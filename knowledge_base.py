import chromadb
import chromadb.utils.embedding_functions as embedding_functions
import os
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

def get_openai_key():
    try:
        if "OPENAI_API_KEY" in st.secrets:
            return st.secrets["OPENAI_API_KEY"]
    except Exception:
        pass
    return os.getenv("OPENAI_API_KEY")

# Initialize OpenAI embedding function
openai_ef = embedding_functions.OpenAIEmbeddingFunction(
    api_key=get_openai_key(),
    model_name="text-embedding-3-small"
)

# Initialize ChromaDB (creates a local folder named 'chroma_db' to save data)
chroma_client = chromadb.PersistentClient(path="./chroma_db")

# Get or create a collection (like a table in a database)
collection = chroma_client.get_or_create_collection(
    name="setup_guide_materials", 
    embedding_function=openai_ef
)

def populate_database():
    """Reads the Markdown file and stores it in ChromaDB."""
    # Check if we already populated it to avoid duplicates
    if collection.count() > 0:
        return
        
    try:
        with open("SETUP_GUIDE 3.md", "r", encoding="utf-8") as file:
            text = file.read()
            
        # Chunking: Split by double newlines to keep markdown paragraphs/code blocks intact
        chunks = text.split("\n\n")
        
        # Filter out any empty chunks
        chunks = [chunk.strip() for chunk in chunks if chunk.strip()]
        
        # Add chunks to ChromaDB
        collection.add(
            documents=chunks,
            metadatas=[{"source": "SETUP_GUIDE 3"} for _ in chunks],
            ids=[f"chunk_{i}" for i in range(len(chunks))]
        )
        print("Knowledge base populated successfully!")
    except FileNotFoundError:
        print("Error: 'SETUP_GUIDE 3.md' not found in the directory.")

def search_course_material(query):
    """The tool function the AI will use to search the database."""
    results = collection.query(
        query_texts=[query],
        n_results=3 # Return the top 3 most relevant paragraphs
    )
    
    if not results['documents'][0]:
        return "No relevant information found in the setup guide."
        
    # Combine the top results into a single string
    retrieved_context = "\n\n".join(results['documents'][0])
    return retrieved_context

# Run this once when the module loads to ensure DB has data
populate_database()