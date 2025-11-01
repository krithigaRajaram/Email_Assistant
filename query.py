import os
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

def load_vectorstore():
    embeddings = OpenAIEmbeddings(
        model="text-embedding-3-small",
        openai_api_base="https://models.inference.ai.azure.com",
        openai_api_key=GITHUB_TOKEN
    )
    vectorstore = Chroma(
        persist_directory="./chroma_db",
        embedding_function=embeddings
    )
    print(f"Loaded {vectorstore._collection.count()} vectors\n")
    return vectorstore

def create_rag_chain(vectorstore):
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        openai_api_base="https://models.inference.ai.azure.com",
        openai_api_key=GITHUB_TOKEN,
        temperature=0
    )
    
    retriever = vectorstore.as_retriever(search_kwargs={"k": 3})
    
    template = """Answer the question based on the following context:

Context: {context}

Question: {question}

Answer:"""
    
    prompt = ChatPromptTemplate.from_template(template)
    
    rag_chain = (
        {"context": retriever, "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )
    
    return rag_chain

def query_emails(rag_chain, question):
    result = rag_chain.invoke(question)
    print(f"Q: {question}")
    print(f"A: {result}\n")

def main():
    vectorstore = load_vectorstore()
    rag_chain = create_rag_chain(vectorstore)
    
    while True:
        question = input("Your question (or 'quit'): ").strip()
        if question.lower() in ['quit', 'exit', 'q']:
            break
        if question:
            query_emails(rag_chain, question)

if __name__ == "__main__":
    main()