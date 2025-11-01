import os
from dotenv import load_dotenv
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma

load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
#load the text file
def load_emails():    
    loader = DirectoryLoader(
        './data',
        glob="*.txt",
        loader_cls=TextLoader
    )
    documents = loader.load()
    print(f"{len(documents)} emails")
    return documents
#split to chunks
def split_documents(documents):
    text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200,
    length_function=len,
    )
    chunks = text_splitter.split_documents(documents)
    print(f"{len(chunks)} chunks")
    return chunks
#Vectorize and store in ChromaDB
def create_vectorstore(chunks):
    embeddings = OpenAIEmbeddings(
        model="text-embedding-3-small",
        openai_api_base="https://models.inference.ai.azure.com",
        openai_api_key=GITHUB_TOKEN
    )
    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory="./chroma_db"
    )
    print(f" {vectorstore._collection.count()} vectors in ChromaDB")
    return vectorstore

def main():
    documents = load_emails()
    chunks = split_documents(documents)
    vectorstore = create_vectorstore(chunks)
    print("SUCCESS! Your vector database is ready.")

if __name__ == "__main__":
    main()