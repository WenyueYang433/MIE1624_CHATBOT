import os
from dotenv import load_dotenv
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS

load_dotenv()

DATA_DIR = "data"
INDEX_DIR = "faiss_index"

def load_docs():
    docs = []
    for name in os.listdir(DATA_DIR):
        path = os.path.join(DATA_DIR, name)
        if name.endswith(".md") or name.endswith(".txt"):
            docs.extend(TextLoader(path, encoding="utf-8").load())
    return docs

def main():
    docs = load_docs()
    if not docs:
        raise ValueError("No documents found in ./data. Put your Part1-4 summaries there.")
    splitter = RecursiveCharacterTextSplitter(chunk_size=900, chunk_overlap=150)
    chunks = splitter.split_documents(docs)
    embeddings = OpenAIEmbeddings()
    db = FAISS.from_documents(chunks, embeddings)
    db.save_local(INDEX_DIR)
    print(f"Index built and saved to ./{INDEX_DIR}")

if __name__ == "__main__":
    main()