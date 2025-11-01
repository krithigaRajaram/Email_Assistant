from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import os
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

load_dotenv()

app = FastAPI(title="Email RAG API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variables
vectorstore = None
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

class QueryRequest(BaseModel):
    question: str
    k: Optional[int] = 5

class QueryResponse(BaseModel):
    question: str
    answer: str
    sources: List[dict]

def detect_counting_question(question):
    """Detect if question asks for counting"""
    counting_keywords = ['how many', 'count', 'total', 'number of', 'how much', 'sum', 'all', 'list all']
    return any(keyword in question.lower() for keyword in counting_keywords)

def create_rag_chain(k=5):
    """Create RAG chain"""
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        openai_api_base="https://models.inference.ai.azure.com",
        openai_api_key=GITHUB_TOKEN,
        temperature=0,
        max_tokens=1000
    )
    
    retriever = vectorstore.as_retriever(search_kwargs={"k": k})
    
    template = """Answer the question based on the following context from emails:

Context: {context}

Question: {question}

Instructions:
- For counting questions: Count unique emails by their Subject + From + Date combination. Give a direct answer.
- For content questions: Answer directly and concisely.
- Be confident and direct in your answers.

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
    """Initialize vector store"""
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
    
    print(f"✅ Loaded {vectorstore._collection.count()} vectors")

@app.on_event("startup")
async def startup_event():
    """Initialize on startup"""
    print("Starting Email RAG API...")
    initialize_vectorstore()
    print("✅ API ready!")

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Email RAG API",
        "version": "1.0.0",
        "endpoints": {
            "docs": "/docs",
            "health": "/health",
            "stats": "/stats",
            "query": "/query (POST)"
        }
    }

@app.post("/query", response_model=QueryResponse)
async def query_emails(request: QueryRequest):
    """Query emails using RAG"""
    if not vectorstore:
        raise HTTPException(status_code=500, detail="Vector store not initialized")
    
    try:
        # Adjust k based on question type
        k = 20 if detect_counting_question(request.question) else request.k
        
        # Create RAG chain and retriever
        rag_chain, retriever = create_rag_chain(k=k)
        
        # Get answer
        answer = rag_chain.invoke(request.question)
        
        # Get source documents - FIXED METHOD
        source_docs = retriever.invoke(request.question) 
        
        sources = [
            {
                "subject": doc.metadata.get("subject", "Unknown"),
                "from": doc.metadata.get("from", "Unknown"),
                "date": doc.metadata.get("date", "Unknown"),
                "snippet": doc.page_content[:200] + "..."
            }
            for doc in source_docs[:5]  # Limit to 5 sources
        ]
        
        return QueryResponse(
            question=request.question,
            answer=answer,
            sources=sources
        )
        
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "vector_count": vectorstore._collection.count() if vectorstore else 0
    }

@app.get("/stats")
async def get_stats():
    """Get statistics"""
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