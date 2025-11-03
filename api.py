from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from typing import List, Optional
import os
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

load_dotenv()

app = FastAPI(title="Email RAG API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="frontend"), name="static")

vectorstore = None
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

class QueryRequest(BaseModel):
    question: str
    k: Optional[int] = 5

class QueryResponse(BaseModel):
    question: str
    answer: str
    sources: List[dict]

def is_valid_question(question):
    question = question.strip().lower()
    
    if len(question) < 3:
        return False
    
    if len(question.split()) < 2:
        return False
    
    gibberish_patterns = ['asdf', 'qwerty', 'zxcv', 'test', 'hello', 'hi']
    if question in gibberish_patterns:
        return False
    
    return True

def detect_counting_question(question):
    counting_keywords = ['how many', 'count', 'total', 'number of', 'how much', 'sum', 'all', 'list all']
    return any(keyword in question.lower() for keyword in counting_keywords)

def create_rag_chain(k=5):
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        openai_api_base="https://models.inference.ai.azure.com",
        openai_api_key=GITHUB_TOKEN,
        temperature=0,
        max_tokens=50  
    )
    
    retriever = vectorstore.as_retriever(
        search_kwargs={"k": k},
        search_type="similarity"
    )
    
    template = """Context: {context}

Question: {question}

Give ONLY the final answer. No explanations, no calculations shown, no breakdown.

Answer format examples:
- "How many emails?" → "5 emails"
- "Total spent?" → "₹1,126.71"
- "Latest order?" → "₹202.70 on Oct 30"

Answer:"""
    
    prompt = ChatPromptTemplate.from_template(template)
    
    rag_chain = (
        {"context": retriever, "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )
    
    return rag_chain, retriever

def initialize_vectorstore():
    global vectorstore
    
    embeddings = OpenAIEmbeddings(
        model="text-embedding-3-small",
        openai_api_base="https://models.inference.ai.azure.com",
        openai_api_key=GITHUB_TOKEN
    )
    
    vectorstore = Chroma(
        persist_directory="./chroma_db",
        embedding_function=embeddings
    )

@app.on_event("startup")
async def startup_event():
    initialize_vectorstore()

@app.get("/")
async def root():
    return RedirectResponse(url="/static/index.html")

@app.post("/query", response_model=QueryResponse)
async def query_emails(request: QueryRequest):
    if not vectorstore:
        raise HTTPException(status_code=500, detail="Vector store not initialized")
    
    if not is_valid_question(request.question):
        return QueryResponse(
            question=request.question,
            answer="Please ask a proper question about your emails. For example: 'How many emails from Zomato?' or 'What's my latest order?'",
            sources=[]
        )
    
    try:
        k = 20 if detect_counting_question(request.question) else request.k
        rag_chain, retriever = create_rag_chain(k=k)
        answer = rag_chain.invoke(request.question)
        
        if "don't have information" in answer.lower() or "don't know" in answer.lower():
            return QueryResponse(
                question=request.question,
                answer=answer,
                sources=[]
            )
        
        source_docs = retriever.invoke(request.question)
        
        sources = [
            {
                "subject": doc.metadata.get("subject", "Unknown"),
                "from": doc.metadata.get("from", "Unknown"),
                "date": doc.metadata.get("date", "Unknown"),
                "snippet": doc.page_content[:200] + "..."
            }
            for doc in source_docs[:5]
        ]
        
        return QueryResponse(
            question=request.question,
            answer=answer,
            sources=sources
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "vector_count": vectorstore._collection.count() if vectorstore else 0
    }

@app.get("/stats")
async def get_stats():
    if not vectorstore:
        raise HTTPException(status_code=500, detail="Vector store not initialized")
    
    return {
        "total_vectors": vectorstore._collection.count(),
        "total_emails": "~500",
        "database_path": "./chroma_db"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)