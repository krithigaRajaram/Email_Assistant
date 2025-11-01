from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import base64
import os
import pickle

class GmailFetcher:
    SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
    
    def __init__(self):
        self.service = self.authenticate()
    
    def authenticate(self):
        """Authenticate with Gmail API"""
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
        """Fetch emails with optional query filter"""
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
        """Get full email content"""
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
            body = self.get_message_body(message['payload'])
            
            return {
                'id': msg_id,
                'subject': subject,
                'from': sender,
                'date': date,
                'body': body
            }
        except:
            return None
    
    def get_message_body(self, payload):
        """Extract email body from payload"""
        if 'body' in payload and payload['body'].get('data'):
            return base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8', errors='ignore')
        
        if 'parts' in payload:
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain':
                    if 'data' in part['body']:
                        return base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='ignore')
                elif 'parts' in part:
                    body = self.get_message_body(part)
                    if body:
                        return body
        
        return ""

if __name__ == "__main__":
    fetcher = GmailFetcher()
    emails = fetcher.fetch_emails(max_results=5)
    
    for i, email in enumerate(emails[:3], 1):
        print(f"\nEmail {i}:")
        print(f"Subject: {email['subject']}")
        print(f"From: {email['from']}")
        print(f"Date: {email['date']}")