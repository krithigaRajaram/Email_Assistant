import os
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

def load_vectorstore():
    """Load existing vector store"""
    embeddings = OpenAIEmbeddings(
        model="text-embedding-3-small",
        openai_api_base="https://models.inference.ai.azure.com",
        openai_api_key=GITHUB_TOKEN
    )
    
    vectorstore = Chroma(
        persist_directory="./chroma_db",
        embedding_function=embeddings
    )
    
    return vectorstore

def detect_counting_question(question):
    """Detect if question asks for counting/aggregation"""
    counting_keywords = [
        'how many', 'count', 'total', 'number of',
        'how much', 'sum', 'all', 'list all'
    ]
    question_lower = question.lower()
    return any(keyword in question_lower for keyword in counting_keywords)

def create_rag_chain(vectorstore, k=3):
    """Create RAG chain for querying"""
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
- For counting questions: Count unique emails by their Subject + From + Date combination. Give a direct answer without phrases like "based on the sample" or "approximately".
- For content questions: Answer directly and concisely.
- Use information from the emails provided.
- Be confident and direct in your answers.

Answer:"""
    
    prompt = ChatPromptTemplate.from_template(template)
    
    rag_chain = (
        {"context": retriever, "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )
    
    return rag_chain

def query_emails(vectorstore, question):
    """Query the email database with smart k selection"""
    k = 20 if detect_counting_question(question) else 5
    
    try:
        rag_chain = create_rag_chain(vectorstore, k=k)
        result = rag_chain.invoke(question)
        print(f"\n{result}\n")
        
    except Exception as e:
        if "tokens_limit_reached" in str(e) or "413" in str(e):
            # Retry with smaller k
            rag_chain = create_rag_chain(vectorstore, k=10)
            result = rag_chain.invoke(question)
            print(f"\n{result}\n")
        else:
            print(f"\nError: {e}\n")

def main():
    print("Email RAG Query System")
    print("-" * 40)
    
    vectorstore = load_vectorstore()
    print("Ready! Type 'quit' to exit.\n")
    
    while True:
        question = input("Question: ").strip()
        
        if question.lower() in ['quit', 'exit', 'q']:
            print("Have a Nice Day!")
            break
        
        if question:
            query_emails(vectorstore, question)

if __name__ == "__main__":
    main()