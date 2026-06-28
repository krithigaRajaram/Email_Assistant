"""
api.py — MailMate AI FastAPI backend
Run: uvicorn api:app --reload --port 8000
"""

from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_chroma import Chroma
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_openai import ChatOpenAI
from langchain_cohere import CohereEmbeddings
from pydantic import BaseModel
from typing import List, Optional

load_dotenv()

GITHUB_TOKEN   = os.getenv("GITHUB_TOKEN")
COHERE_API_KEY = os.getenv("COHERE_API_KEY")
CHROMA_DIR     = "./chroma_db"
vectorstore  = None


# ── Lifespan ───────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    global vectorstore
    if not GITHUB_TOKEN:
        raise RuntimeError("GITHUB_TOKEN not set.")
    embeddings = CohereEmbeddings(
        model="embed-english-v3.0",
        cohere_api_key=COHERE_API_KEY,
    )
    vectorstore = Chroma(persist_directory=CHROMA_DIR, embedding_function=embeddings)
    print(f"Vector store loaded — {vectorstore._collection.count()} vectors.")
    yield


# ── App ────────────────────────────────────────────────────────────────────────

app = FastAPI(title="MailMate AI", version="4.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)


# ── Schemas ────────────────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    question: str
    k: Optional[int] = 5

class QueryResponse(BaseModel):
    question: str
    answer: str
    sources: List[dict]


# ── Intent detection ───────────────────────────────────────────────────────────

def detect_intent(q: str):
    q = q.lower()
    if any(w in q for w in ["today", "this morning", "tonight"]):
        return "today"
    if any(w in q for w in ["yesterday"]):
        return "yesterday"
    if any(w in q for w in ["this week", "past week", "last 7 days"]):
        return "week"
    if any(w in q for w in ["this month", "past month", "last 30 days"]):
        return "month"
    if any(w in q for w in ["latest", "recent", "newest", "last email", "most recent"]):
        return "recent"
    if any(w in q for w in ["how many", "count", "total", "number of", "list all"]):
        return "count"
    return "general"


def get_cutoff_timestamp(intent: str) -> Optional[int]:
    now = datetime.now()
    if intent == "today":
        return int(datetime(now.year, now.month, now.day).timestamp())
    if intent == "yesterday":
        d = now - timedelta(days=1)
        return int(datetime(d.year, d.month, d.day).timestamp())
    if intent == "week":
        return int((now - timedelta(days=7)).timestamp())
    if intent == "month":
        return int((now - timedelta(days=30)).timestamp())
    if intent == "recent":
        return int((now - timedelta(days=14)).timestamp())
    return None


# ── Smart retrieval ────────────────────────────────────────────────────────────

def doc_timestamp(doc) -> int:
    ts = doc.metadata.get("timestamp", 0)
    if ts and ts > 0:
        return ts
    try:
        return int(parsedate_to_datetime(doc.metadata.get("date", "")).timestamp())
    except Exception:
        return 0


def retrieve_docs(question: str, intent: str, k: int):
    cutoff = get_cutoff_timestamp(intent)

    if cutoff:
        # Try filtered retrieval first
        try:
            docs = vectorstore.as_retriever(
                search_type="similarity",
                search_kwargs={"k": k, "filter": {"timestamp": {"$gte": cutoff}}},
            ).invoke(question)
            if docs:
                docs.sort(key=doc_timestamp, reverse=True)
                return docs
        except Exception:
            pass

    # Fallback: plain similarity, sort by date
    docs = vectorstore.as_retriever(
        search_type="similarity",
        search_kwargs={"k": k},
    ).invoke(question)

    if intent in ("today", "yesterday", "week", "month", "recent"):
        docs.sort(key=doc_timestamp, reverse=True)

    return docs


# ── Prompt & chain ─────────────────────────────────────────────────────────────

PROMPT = """You are MailMate AI, a precise email assistant.
Answer using ONLY the emails provided in the context below.

Today's date : {today}
Yesterday    : {yesterday}

Emails (sorted newest first):
{context}

Question: {question}

Rules:
- For "latest N emails" → list the top N by date from the context.
- For "today" → look for emails where the Date contains "{today_short}". If you find any, list them. Do not say there are none if they appear in the context.
- For "yesterday" → look for emails where the Date contains "{yesterday_short}".
- For counting → count unique emails by Subject + From + Date.
- Never invent emails not in the context.
- Always trust the email dates in the context over your own reasoning.

Answer:"""


def build_answer(docs, question: str) -> str:
    # Sort newest first before passing to LLM
    docs_sorted = sorted(docs, key=doc_timestamp, reverse=True)
    context     = "\n\n---\n\n".join(d.page_content for d in docs_sorted)

    now            = datetime.now()
    yesterday      = now - timedelta(days=1)
    today_str      = now.strftime("%A, %d %B %Y")
    yesterday_str  = yesterday.strftime("%A, %d %B %Y")
    today_short    = now.strftime("%d %b %Y")
    yesterday_short= yesterday.strftime("%d %b %Y")

    llm    = ChatOpenAI(
        model="gpt-4o-mini",
        openai_api_base="https://models.inference.ai.azure.com",
        openai_api_key=GITHUB_TOKEN,
        temperature=0, max_tokens=1000,
    )
    prompt = ChatPromptTemplate.from_template(PROMPT)
    chain  = (
        {
            "context":          lambda _: context,
            "question":         RunnablePassthrough(),
            "today":            lambda _: today_str,
            "yesterday":        lambda _: yesterday_str,
            "today_short":      lambda _: today_short,
            "yesterday_short":  lambda _: yesterday_short,
        }
        | prompt | llm | StrOutputParser()
    )
    return chain.invoke(question)


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    count = vectorstore._collection.count() if vectorstore else 0
    return {"status": "healthy", "vector_count": count}


@app.get("/stats")
async def stats():
    if not vectorstore:
        raise HTTPException(500, "Vector store not initialised.")
    return {"total_vectors": vectorstore._collection.count(), "database_path": CHROMA_DIR}


@app.post("/query", response_model=QueryResponse)
async def query_emails(request: QueryRequest):
    if not vectorstore:
        raise HTTPException(500, "Vector store not initialised.")

    question = request.question.strip()
    if not question:
        raise HTTPException(400, "Question cannot be empty.")

    intent = detect_intent(question)
    k      = 20 if intent in ("count", "today", "yesterday", "week", "month") else request.k

    try:
        docs    = retrieve_docs(question, intent, k)
        answer  = build_answer(docs, question)
        sources = [
            {
                "subject": d.metadata.get("subject", "Unknown"),
                "from":    d.metadata.get("from", "Unknown"),
                "date":    d.metadata.get("date", "Unknown"),
                "snippet": d.page_content[:200] + "...",
            }
            for d in docs[:5]
        ]
        return QueryResponse(question=question, answer=answer, sources=sources)
    except Exception as e:
        raise HTTPException(500, str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)