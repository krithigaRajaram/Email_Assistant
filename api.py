"""
api.py

FastAPI backend for Email RAG Assistant.
Run with: uvicorn api:app --reload --port 8000
"""

from contextlib import asynccontextmanager
import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_chroma import Chroma
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from pydantic import BaseModel
from typing import List, Optional

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
CHROMA_DIR = "./chroma_db"

vectorstore = None


# ── Lifespan (replaces deprecated @app.on_event) ──────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    global vectorstore
    if not GITHUB_TOKEN:
        raise RuntimeError("GITHUB_TOKEN not set in .env file.")

    embeddings = OpenAIEmbeddings(
        model="text-embedding-3-small",
        openai_api_base="https://models.inference.ai.azure.com",
        openai_api_key=GITHUB_TOKEN,
    )
    vectorstore = Chroma(
        persist_directory=CHROMA_DIR,
        embedding_function=embeddings,
    )
    print(f"Vector store loaded — {vectorstore._collection.count()} vectors.")
    yield
    # cleanup (nothing needed for Chroma)


app = FastAPI(title="Email RAG API", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



class QueryRequest(BaseModel):
    question: str
    k: Optional[int] = 5


class SourceItem(BaseModel):
    subject: str
    from_: str
    date: str
    snippet: str


class QueryResponse(BaseModel):
    question: str
    answer: str
    sources: List[dict]



def detect_counting_question(question: str) -> bool:
    keywords = ["how many", "count", "total", "number of", "how much", "sum", "list all", "all emails"]
    return any(kw in question.lower() for kw in keywords)


def build_rag_chain(k: int):
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        openai_api_base="https://models.inference.ai.azure.com",
        openai_api_key=GITHUB_TOKEN,
        temperature=0,
        max_tokens=1000,   # Fixed: was 50, which cut off answers
    )

    retriever = vectorstore.as_retriever(
        search_type="similarity",
        search_kwargs={"k": k},
    )

    template = """You are an email assistant. Answer the user's question using only the email context below.

Context:
{context}

Question: {question}

Instructions:
- Answer directly and confidently.
- For counting questions, count unique emails by Subject + From + Date and give a precise number.
- For content questions, summarise clearly.
- If the context doesn't contain enough information, say so honestly.

Answer:"""

    prompt = ChatPromptTemplate.from_template(template)

    chain = (
        {"context": retriever, "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )

    return chain, retriever


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    count = vectorstore._collection.count() if vectorstore else 0
    return {"status": "healthy", "vector_count": count}


@app.get("/stats")
async def stats():
    if not vectorstore:
        raise HTTPException(status_code=500, detail="Vector store not initialised.")
    return {
        "total_vectors": vectorstore._collection.count(),
        "database_path": CHROMA_DIR,
    }


@app.post("/query", response_model=QueryResponse)
async def query_emails(request: QueryRequest):
    if not vectorstore:
        raise HTTPException(status_code=500, detail="Vector store not initialised.")

    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    # Use more context for counting/aggregation questions
    k = 20 if detect_counting_question(question) else request.k

    try:
        chain, retriever = build_rag_chain(k=k)
        answer = chain.invoke(question)

        source_docs = retriever.invoke(question)
        sources = [
            {
                "subject": doc.metadata.get("subject", "Unknown"),
                "from": doc.metadata.get("from", "Unknown"),
                "date": doc.metadata.get("date", "Unknown"),
                "snippet": doc.page_content[:200] + "...",
            }
            for doc in source_docs[:5]
        ]

        return QueryResponse(question=question, answer=answer, sources=sources)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)