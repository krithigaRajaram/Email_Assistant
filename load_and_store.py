"""
load_and_store.py

Fetches ALL emails from Gmail and stores them in ChromaDB incrementally.
- Handles GitHub Models rate limits with automatic retry + delay
- Skips already-stored emails (safe to re-run)
- Processes in batches to avoid memory issues
"""

import os
import time
import json

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from email_fetcher import GmailFetcher

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
CHROMA_DIR = "./chroma_db"
PROGRESS_FILE = "./processed_ids.json"  # tracks already-stored email IDs
EMBED_BATCH_SIZE = 25   # reduced batch size to avoid rate limits
EMBED_DELAY = 5.0       # seconds between embedding batches
MAX_EMAILS = 3000      # cap per user
LOOKBACK_DAYS = 365    # fetch emails from the past 1 year


def load_progress():
    """Load set of already-processed email IDs."""
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r") as f:
            return set(json.load(f))
    return set()


def save_progress(processed_ids):
    """Persist processed email IDs to disk."""
    with open(PROGRESS_FILE, "w") as f:
        json.dump(list(processed_ids), f)


def get_embeddings():
    return OpenAIEmbeddings(
        model="text-embedding-3-small",
        openai_api_base="https://models.inference.ai.azure.com",
        openai_api_key=GITHUB_TOKEN,
        chunk_size=EMBED_BATCH_SIZE,
    )


def get_vectorstore(embeddings):
    return Chroma(
        persist_directory=CHROMA_DIR,
        embedding_function=embeddings,
    )


def emails_to_documents(emails):
    """Convert email dicts to LangChain Documents."""
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
                "id": email["id"],
                "subject": email["subject"],
                "from": email["from"],
                "date": email["date"],
            },
        )
        documents.append(doc)
    return documents


def split_documents(documents):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len,
    )
    return splitter.split_documents(documents)


def store_chunks_with_retry(vectorstore, chunks, max_retries=3):
    """Store chunks with exponential backoff on rate limit errors."""
    for attempt in range(max_retries):
        try:
            vectorstore.add_documents(chunks)
            return True
        except Exception as e:
            err = str(e)
            if "rate" in err.lower() or "429" in err or "limit" in err.lower():
                wait = (attempt + 1) * 30  # 30s, 60s, 90s
                print(f"  Rate limit hit. Waiting {wait}s before retry...")
                time.sleep(wait)
            else:
                print(f"  Error storing batch: {e}")
                return False
    print("  Failed after max retries. Skipping this batch.")
    return False


def main():
    print("=" * 50)
    print("Email RAG — Full Load & Store")
    print("=" * 50)

    if not GITHUB_TOKEN:
        print("ERROR: GITHUB_TOKEN not found in .env file.")
        print("Create a .env file with: GITHUB_TOKEN=your_token_here")
        return

    # Load progress (so we can resume if interrupted)
    processed_ids = load_progress()
    if processed_ids:
        print(f"Resuming — {len(processed_ids)} emails already stored. Skipping those.")

    embeddings = get_embeddings()
    vectorstore = get_vectorstore(embeddings)

    fetcher = GmailFetcher()
    total_stored = 0
    total_skipped = 0

    # Fetch and process all emails page by page
    print(f"Limit  : {MAX_EMAILS} emails / past {LOOKBACK_DAYS} days")
    print()

    for email_batch in fetcher.fetch_all_emails(
        batch_size=100,
        max_emails=MAX_EMAILS,
        days=LOOKBACK_DAYS,
    ):

        # Filter out already-processed emails
        new_emails = [e for e in email_batch if e["id"] not in processed_ids]
        total_skipped += len(email_batch) - len(new_emails)

        if not new_emails:
            continue

        # Convert → split → store
        documents = emails_to_documents(new_emails)
        chunks = split_documents(documents)

        print(f"  Storing {len(chunks)} chunks from {len(new_emails)} new emails...")

        # Store in sub-batches to respect rate limits
        for i in range(0, len(chunks), EMBED_BATCH_SIZE):
            sub_batch = chunks[i : i + EMBED_BATCH_SIZE]
            success = store_chunks_with_retry(vectorstore, sub_batch)
            if success:
                time.sleep(EMBED_DELAY)  # polite delay between batches

        # Mark these emails as processed
        for e in new_emails:
            processed_ids.add(e["id"])
        save_progress(processed_ids)

        total_stored += len(new_emails)

        # Stop if we've hit the global cap
        if len(processed_ids) >= MAX_EMAILS:
            print(f"  Reached {MAX_EMAILS}-email limit. Stopping.")
            break

    print()
    print("=" * 50)
    print(f"Done!")
    print(f"  Emails stored this run : {total_stored}")
    print(f"  Emails skipped (cached): {total_skipped}")
    print(f"  Total vectors in DB    : {vectorstore._collection.count()}")
    print("=" * 50)


if __name__ == "__main__":
    main()