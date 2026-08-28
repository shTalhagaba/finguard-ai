import os

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_google_genai import (
    GoogleGenerativeAIEmbeddings,
    ChatGoogleGenerativeAI,
)

load_dotenv()

CHROMA_DB_PATH = "chroma_db"


def get_embeddings():
    api_key = os.getenv("GOOGLE_API_KEY")

    if not api_key:
        raise ValueError("GOOGLE_API_KEY is missing. Check your .env file.")

    return GoogleGenerativeAIEmbeddings(
        model="models/gemini-embedding-001",
        google_api_key=api_key,
    )


def get_vector_store():
    embeddings = get_embeddings()

    return Chroma(
        collection_name="finguard_documents",
        embedding_function=embeddings,
        persist_directory=CHROMA_DB_PATH,
    )


def add_document_chunks(chunks, filename: str):
    vector_store = get_vector_store()

    documents = [
        Document(
            page_content=chunk,
            metadata={
                "filename": filename,
                "chunk_index": index,
            },
        )
        for index, chunk in enumerate(chunks)
    ]

    vector_store.add_documents(documents)

    return len(documents)


def search_documents(query: str, k: int = 4):
    vector_store = get_vector_store()

    return vector_store.similarity_search(
        query=query,
        k=k,
    )


def generate_answer(query: str):
    results = search_documents(query)

    if not results:
        return {
            "answer": "I couldn't find relevant information in the uploaded documents.",
            "sources": [],
        }

    context = "\n\n---\n\n".join(
        [
            f"Source: {doc.metadata.get('filename', 'Unknown')}\n"
            f"Content: {doc.page_content}"
            for doc in results
        ]
    )

    api_key = os.getenv("GOOGLE_API_KEY")

    if not api_key:
        raise ValueError("GOOGLE_API_KEY is missing. Check your .env file.")

    llm = ChatGoogleGenerativeAI(
        model="gemini-3.6-flash",
        google_api_key=api_key,
        temperature=0.2,
    )

    prompt = f"""You are FinGuard AI, an intelligent document assistant.

Answer the user's question using ONLY the provided document context.

Rules:
- Do not invent information.
- Do not use outside knowledge.
- If the answer is not available in the context, clearly say so.
- Keep the answer clear and professional.

DOCUMENT CONTEXT:
{context}

USER QUESTION:
{query}
"""

    response = llm.invoke(prompt)

    sources = [
        {
            "filename": doc.metadata.get("filename"),
            "chunk_index": doc.metadata.get("chunk_index"),
        }
        for doc in results
    ]

    return {
        "answer": response.content,
        "sources": sources,
    }
