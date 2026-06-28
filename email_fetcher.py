import base64
import os
import pickle
import re

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False
    print("Warning: BeautifulSoup not installed. Run: pip install beautifulsoup4")


class GmailFetcher:
    # Read-only access to all mail
    SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

    def __init__(self):
        self.service = self._authenticate()

    def _authenticate(self):
        creds = None

        if os.path.exists("token.pickle"):
            with open("token.pickle", "rb") as f:
                creds = pickle.load(f)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    "credentials.json", self.SCOPES
                )
                flow.redirect_uri = "urn:ietf:wg:oauth:2.0:oob"
                auth_url, _ = flow.authorization_url(prompt='consent')
                print("\n" + "="*60)
                print("GMAIL AUTHENTICATION REQUIRED")
                print("="*60)
                print("\n1. Copy and open this URL in your browser:\n")
                print(auth_url)
                print("\n2. Sign in with your Google account")
                print("3. Click Allow")
                print("4. Google will show you a CODE (short string)")
                print("="*60)
                code = input("\nPaste the code here: ").strip()
                flow.fetch_token(code=code)
                creds = flow.credentials

            with open("token.pickle", "wb") as f:
                pickle.dump(creds, f)

        return build("gmail", "v1", credentials=creds)

    def fetch_latest(self, max_emails=300):
        """Fetch the latest max_emails emails, newest first. Used for initial load."""
        print(f"Fetching latest {max_emails} emails (newest first)...")
        emails     = []
        page_token = None

        while len(emails) < max_emails:
            fetch_size = min(100, max_emails - len(emails))
            params = {
                "userId": "me",
                "maxResults": fetch_size,
                "includeSpamTrash": False,
            }
            if page_token:
                params["pageToken"] = page_token

            results  = self.service.users().messages().list(**params).execute()
            messages = results.get("messages", [])
            if not messages:
                break

            for msg in messages:
                if len(emails) >= max_emails:
                    break
                data = self._get_email_content(msg["id"])
                if data:
                    emails.append(data)

            print(f"  Fetched {len(emails)}/{max_emails}...")
            page_token = results.get("nextPageToken")
            if not page_token or len(emails) >= max_emails:
                break

        print(f"Done. Total fetched: {len(emails)}")
        return emails

    def fetch_after(self, after_date_str, batch_size=100):
        """Fetch emails after after_date_str (YYYY/MM/DD). Yields batches. Used for incremental sync."""
        query         = f"after:{after_date_str}"
        page_token    = None
        total_fetched = 0

        print(f"Incremental sync: fetching emails after {after_date_str}...")

        while True:
            params = {
                "userId": "me",
                "maxResults": batch_size,
                "q": query,
                "includeSpamTrash": False,
            }
            if page_token:
                params["pageToken"] = page_token

            results  = self.service.users().messages().list(**params).execute()
            messages = results.get("messages", [])
            if not messages:
                break

            batch = []
            for msg in messages:
                data = self._get_email_content(msg["id"])
                if data:
                    batch.append(data)

            total_fetched += len(batch)
            print(f"  Fetched {total_fetched} new emails so far...")
            yield batch

            page_token = results.get("nextPageToken")
            if not page_token:
                break

        print(f"Done. Total new emails fetched: {total_fetched}")

    def _get_email_content(self, msg_id):
        try:
            message = self.service.users().messages().get(
                userId="me", id=msg_id, format="full"
            ).execute()

            headers = message["payload"]["headers"]
            subject = next(
                (h["value"] for h in headers if h["name"] == "Subject"), "No Subject"
            )
            sender = next(
                (h["value"] for h in headers if h["name"] == "From"), "Unknown"
            )
            date = next(
                (h["value"] for h in headers if h["name"] == "Date"), "Unknown"
            )

            body_html = self._get_message_body(message["payload"], prefer_html=True)
            body_text = self._get_message_body(message["payload"], prefer_html=False)

            if body_html and "<html" in body_html.lower():
                parsed_body = self._extract_text_from_html(body_html)
            else:
                parsed_body = body_text or body_html or ""

            return {
                "id": msg_id,
                "subject": subject,
                "from": sender,
                "date": date,
                "body": parsed_body,
            }
        except Exception as e:
            print(f"  Error processing email {msg_id}: {e}")
            return None

    def _get_message_body(self, payload, prefer_html=True):
        if "body" in payload and payload["body"].get("data"):
            return base64.urlsafe_b64decode(
                payload["body"]["data"]
            ).decode("utf-8", errors="ignore")

        if "parts" in payload:
            html_content = None
            text_content = None

            for part in payload["parts"]:
                if part["mimeType"] == "text/html" and "data" in part.get("body", {}):
                    html_content = base64.urlsafe_b64decode(
                        part["body"]["data"]
                    ).decode("utf-8", errors="ignore")
                elif part["mimeType"] == "text/plain" and "data" in part.get("body", {}):
                    text_content = base64.urlsafe_b64decode(
                        part["body"]["data"]
                    ).decode("utf-8", errors="ignore")
                elif "parts" in part:
                    body = self._get_message_body(part, prefer_html)
                    if body:
                        return body

            if prefer_html and html_content:
                return html_content
            elif text_content:
                return text_content
            elif html_content:
                return html_content

        return ""

    def _extract_text_from_html(self, html_body):
        if not html_body:
            return ""

        if not BS4_AVAILABLE:
            return self._simple_html_strip(html_body)

        try:
            soup = BeautifulSoup(html_body, "html.parser")
            for tag in soup(["script", "style", "head", "title", "meta", "link"]):
                tag.decompose()

            text = soup.get_text(separator=" ", strip=True)
            text = re.sub(r"\s+", " ", text)
            text = re.sub(r"\s([.,!?;:])", r"\1", text)
            return text.strip()
        except Exception as e:
            print(f"  HTML parsing error: {e}")
            return self._simple_html_strip(html_body)

    def _simple_html_strip(self, html):
        text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()