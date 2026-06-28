"""
load_and_store.py

Two modes:
  1. Initial load  — fetches latest 300 emails, stores with timestamp metadata
  2. Incremental   — fetches only emails newer than last sync date

Uses Cohere for embeddings (embed-english-v3.0).
Run: python load_and_store.py
"""

import os
import time
import json
from datetime import datetime
from email.utils import parsedate_to_datetime

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_cohere import CohereEmbeddings
from langchain_chroma import Chroma
from email_fetcher import GmailFetcher

load_dotenv()

COHERE_API_KEY   = os.getenv("COHERE_API_KEY")
CHROMA_DIR       = "./chroma_db"
PROGRESS_FILE    = "./processed_ids.json"
SYNC_STATE_FILE  = "./sync_state.json"
EMBED_BATCH_SIZE = 25
EMBED_DELAY      = 2.0
INITIAL_LIMIT    = 300


# ── State helpers ──────────────────────────────────────────────────────────────

def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE) as f:
            return set(json.load(f))
    return set()


def save_progress(ids):
    with open(PROGRESS_FILE, "w") as f:
        json.dump(list(ids), f)


def load_sync_state():
    if os.path.exists(SYNC_STATE_FILE):
        with open(SYNC_STATE_FILE) as f:
            return json.load(f).get("last_sync_date")
    return None


def save_sync_state(date_str):
    with open(SYNC_STATE_FILE, "w") as f:
        json.dump({"last_sync_date": date_str}, f)


# ── Embeddings & vector store ──────────────────────────────────────────────────

def get_embeddings():
    return CohereEmbeddings(
        model="embed-english-v3.0",
        cohere_api_key=COHERE_API_KEY,
    )


def get_vectorstore(embeddings):
    return Chroma(persist_directory=CHROMA_DIR, embedding_function=embeddings)


# ── Document helpers ───────────────────────────────────────────────────────────

def parse_timestamp(date_str):
    try:
        return int(parsedate_to_datetime(date_str).timestamp())
    except Exception:
        return 0


def emails_to_documents(emails):
    docs = []
    for email in emails:
        content = (
            f"Subject: {email['subject']}\n"
            f"From: {email['from']}\n"
            f"Date: {email['date']}\n\n"
            f"{email['body']}"
        )
        docs.append(Document(
            page_content=content,
            metadata={
                "id":        email["id"],
                "subject":   email["subject"],
                "from":      email["from"],
                "date":      email["date"],
                "timestamp": parse_timestamp(email["date"]),
            },
        ))
    return docs


def split_documents(documents):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000, chunk_overlap=200, length_function=len
    )
    return splitter.split_documents(documents)


def store_with_retry(vectorstore, chunks, max_retries=3):
    for attempt in range(max_retries):
        try:
            vectorstore.add_documents(chunks)
            return True
        except Exception as e:
            err = str(e)
            if "rate" in err.lower() or "429" in err or "limit" in err.lower():
                wait = (attempt + 1) * 30
                print(f"  Rate limit hit. Waiting {wait}s...")
                time.sleep(wait)
            else:
                print(f"  Error: {e}")
                return False
    print("  Failed after retries. Skipping batch.")
    return False


def embed_and_store(vectorstore, emails, processed_ids):
    new_emails = [e for e in emails if e["id"] not in processed_ids]
    if not new_emails:
        print("  No new emails to store.")
        return 0

    docs   = emails_to_documents(new_emails)
    chunks = split_documents(docs)
    print(f"  Storing {len(chunks)} chunks from {len(new_emails)} emails...")

    for i in range(0, len(chunks), EMBED_BATCH_SIZE):
        batch   = chunks[i : i + EMBED_BATCH_SIZE]
        success = store_with_retry(vectorstore, batch)
        if success:
            time.sleep(EMBED_DELAY)

    for e in new_emails:
        processed_ids.add(e["id"])
    save_progress(processed_ids)

    return len(new_emails)


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print("=" * 52)
    print("MailMate AI — Email Sync")
    print("=" * 52)

    if not COHERE_API_KEY:
        print("ERROR: COHERE_API_KEY not set in .env")
        return

    processed_ids = load_progress()
    last_sync     = load_sync_state()
    today_str     = datetime.now().strftime("%Y/%m/%d")
    embeddings    = get_embeddings()
    vectorstore   = get_vectorstore(embeddings)
    fetcher       = GmailFetcher()
    total_stored  = 0

    if not last_sync:
        # ── Initial load ───────────────────────────────────────────────────────
        print(f"Mode   : Initial load (latest {INITIAL_LIMIT} emails)")
        print()
        emails       = fetcher.fetch_latest(max_emails=INITIAL_LIMIT)
        total_stored = embed_and_store(vectorstore, emails, processed_ids)

        # Set sync anchor to oldest email date
        if emails:
            timestamps = [parse_timestamp(e["date"]) for e in emails if parse_timestamp(e["date"]) > 0]
            if timestamps:
                oldest_str = datetime.fromtimestamp(min(timestamps)).strftime("%Y/%m/%d")
                save_sync_state(oldest_str)
                print(f"\n  Sync anchor set to: {oldest_str}")
            else:
                save_sync_state(today_str)
        else:
            save_sync_state(today_str)

    else:
        # ── Incremental sync ───────────────────────────────────────────────────
        print(f"Mode   : Incremental sync")
        print(f"Fetching emails after: {last_sync}")
        print(f"Cached : {len(processed_ids)} emails already stored")
        print()

        for batch in fetcher.fetch_after(after_date_str=last_sync):
            stored       = embed_and_store(vectorstore, batch, processed_ids)
            total_stored += stored
            save_sync_state(today_str)

    print()
    print("=" * 52)
    print(f"Done!")
    print(f"  Emails stored this run : {total_stored}")
    print(f"  Total in DB            : {len(processed_ids)}")
    print(f"  Total vectors          : {vectorstore._collection.count()}")
    print(f"  Next sync after        : {today_str}")
    print("=" * 52)


if __name__ == "__main__":
    main()