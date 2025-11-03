from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import base64
import os
import pickle
import re

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False
    print("⚠️  Warning: BeautifulSoup not installed. Install with: pip install beautifulsoup4")

class GmailFetcher:
    SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
    
    def __init__(self):
        self.service = self.authenticate()
    
    def authenticate(self):
        creds = None
        
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', self.SCOPES)
                try:
                    creds = flow.run_local_server(port=0)
                except:
                    creds = flow.run_console()
            
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)
        
        return build('gmail', 'v1', credentials=creds)
    
    def fetch_emails(self, max_results=100, query=''):
        results = self.service.users().messages().list(
            userId='me', 
            maxResults=max_results,
            q=query
        ).execute()
        
        messages = results.get('messages', [])
        if not messages:
            return []
        
        emails = []
        for msg in messages:
            email_data = self.get_email_content(msg['id'])
            if email_data:
                emails.append(email_data)
        
        return emails
    
    def get_email_content(self, msg_id):
        try:
            message = self.service.users().messages().get(
                userId='me', 
                id=msg_id, 
                format='full'
            ).execute()
            
            headers = message['payload']['headers']
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
            sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')
            date = next((h['value'] for h in headers if h['name'] == 'Date'), 'Unknown')
            
            body_html = self.get_message_body(message['payload'], prefer_html=True)
            body_text = self.get_message_body(message['payload'], prefer_html=False)
            
            if body_html and '<html' in body_html.lower():
                parsed_body = self.extract_text_from_html(body_html)
            else:
                parsed_body = body_text or body_html or ""
            
            return {
                'id': msg_id,
                'subject': subject,
                'from': sender,
                'date': date,
                'body': parsed_body
            }
        except Exception as e:
            print(f"Error processing email {msg_id}: {e}")
            return None
    
    def get_message_body(self, payload, prefer_html=True):
        if 'body' in payload and payload['body'].get('data'):
            return base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8', errors='ignore')
        
        if 'parts' in payload:
            html_content = None
            text_content = None
            
            for part in payload['parts']:
                if part['mimeType'] == 'text/html' and 'data' in part['body']:
                    html_content = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='ignore')
                elif part['mimeType'] == 'text/plain' and 'data' in part['body']:
                    text_content = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='ignore')
                elif 'parts' in part:
                    body = self.get_message_body(part, prefer_html)
                    if body:
                        return body
            
            if prefer_html and html_content:
                return html_content
            elif text_content:
                return text_content
            elif html_content:
                return html_content
        
        return ""
    
    def extract_text_from_html(self, html_body):
        if not html_body:
            return ""
        
        if not BS4_AVAILABLE:
            return self.simple_html_strip(html_body)
        
        try:
            soup = BeautifulSoup(html_body, 'html.parser')
            
            for script in soup(['script', 'style', 'head', 'title', 'meta', 'link']):
                script.decompose()
            
            text = soup.get_text(separator=' ', strip=True)
            
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = ' '.join(chunk for chunk in chunks if chunk)
            
            text = re.sub(r'\s+', ' ', text)
            text = re.sub(r'\s([.,!?;:])', r'\1', text)
            
            return text.strip()
            
        except Exception as e:
            print(f"HTML parsing error: {e}")
            return self.simple_html_strip(html_body)
    
    def simple_html_strip(self, html):
        text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

if __name__ == "__main__":
    fetcher = GmailFetcher()
    emails = fetcher.fetch_emails(max_results=5)
    
    for i, email in enumerate(emails[:3], 1):
        print(f"\nEmail {i}:")
        print(f"Subject: {email['subject']}")
        print(f"From: {email['from']}")
        print(f"Body: {email['body'][:500]}...")