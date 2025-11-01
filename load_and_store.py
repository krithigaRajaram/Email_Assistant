import os
from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from email_fetcher import GmailFetcher

load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

def load_emails():
    """Fetch emails from Gmail API"""
    fetcher = GmailFetcher()
    emails = fetcher.fetch_emails(max_results=500)
    
    documents = []
    for email in emails:
        content = f"""Subject: {email['subject']}
From: {email['from']}
Date: {email['date']}

{email['body']}
"""
        doc = Document(
            page_content=content,
            metadata={
                'id': email['id'],
                'subject': email['subject'],
                'from': email['from'],
                'date': email['date']
            }
        )
        documents.append(doc)
    
    return documents

def split_documents(documents):
    """Split documents into chunks"""
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len,
    )
    return text_splitter.split_documents(documents)

def create_vectorstore(chunks):
    """Vectorize and store in ChromaDB with batch processing"""
    embeddings = OpenAIEmbeddings(
        model="text-embedding-3-small",
        openai_api_base="https://models.inference.ai.azure.com",
        openai_api_key=GITHUB_TOKEN,
        chunk_size=100
    )
    
    batch_size = 100
    vectorstore = None
    
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]
        
        if vectorstore is None:
            vectorstore = Chroma.from_documents(
                documents=batch,
                embedding=embeddings,
                persist_directory="./chroma_db"
            )
        else:
            vectorstore.add_documents(batch)
    
    return vectorstore

def main():
    print("Processing emails...")
    
    documents = load_emails()
    if not documents:
        print("No emails found.")
        return
    
    chunks = split_documents(documents)
    vectorstore = create_vectorstore(chunks)
    
    print(f"Done! Processed {len(documents)} emails, {vectorstore._collection.count()} vectors created.")

if __name__ == "__main__":
    main()