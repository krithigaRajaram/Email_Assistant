"""
inspect_db.py

Shows a summary of what's currently stored in ChromaDB.
Reads directly from ChromaDB — no API key or embeddings needed.
"""

import os
import json
from datetime import datetime
from collections import Counter
from email.utils import parsedate_to_datetime

import chromadb

CHROMA_DIR = "./chroma_db"


def parse_date(date_str):
    """Parse email date string to datetime, return None on failure."""
    try:
        return parsedate_to_datetime(date_str)
    except Exception:
        return None


def main():
    print("=" * 55)
    print("MailMate AI — ChromaDB Inspection")
    print("=" * 55)

    if not os.path.exists(CHROMA_DIR):
        print(f"\nNo ChromaDB found at {CHROMA_DIR}")
        return

    # Connect directly to ChromaDB — no embeddings needed
    client     = chromadb.PersistentClient(path=CHROMA_DIR)
    collections = client.list_collections()

    if not collections:
        print("\nNo collections found in ChromaDB.")
        return

    collection    = client.get_collection(collections[0].name)
    total_vectors = collection.count()

    print(f"\nTotal vectors   : {total_vectors:,}")

    if total_vectors == 0:
        print("No data in ChromaDB yet.")
        return

    # Fetch all metadata (no embeddings, just metadata)
    result    = collection.get(include=["metadatas"])
    metadatas = result["metadatas"]

    # Unique emails by ID
    unique_ids = set(m.get("id", "") for m in metadatas)
    print(f"Unique emails   : {len(unique_ids):,}")

    # Date range — try timestamp first, fall back to date string
    dates = []
    for m in metadatas:
        ts = m.get("timestamp", 0)
        if ts and ts > 0:
            dates.append(datetime.fromtimestamp(ts))
        else:
            dt = parse_date(m.get("date", ""))
            if dt:
                dates.append(dt.replace(tzinfo=None))

    if dates:
        oldest = min(dates).strftime("%d %b %Y")
        newest = max(dates).strftime("%d %b %Y")
        print(f"Oldest email    : {oldest}")
        print(f"Newest email    : {newest}")
    else:
        print("Oldest email    : (dates unavailable)")
        print("Newest email    : (dates unavailable)")

    # Top 10 senders
    senders = Counter(m.get("from", "Unknown") for m in metadatas)
    print(f"\nTop 10 senders:")
    for sender, count in senders.most_common(10):
        display = sender if len(sender) <= 50 else sender[:47] + "..."
        print(f"  {count:>5}x  {display}")

    # processed_ids and sync state
    print()
    if os.path.exists("./processed_ids.json"):
        with open("./processed_ids.json") as f:
            cached = json.load(f)
        print(f"processed_ids.json : {len(cached):,} email IDs cached")

    if os.path.exists("./sync_state.json"):
        with open("./sync_state.json") as f:
            sync = json.load(f)
        print(f"Last sync date     : {sync.get('last_sync_date', 'N/A')}")

    print("=" * 55)


if __name__ == "__main__":
    main()