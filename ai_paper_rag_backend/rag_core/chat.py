import os

import chromadb
from llama_index.core import Settings, VectorStoreIndex
from llama_index.embeddings.google_genai import GoogleGenAIEmbedding
from llama_index.llms.google_genai import GoogleGenAI
from llama_index.vector_stores.chroma import ChromaVectorStore

from ai_paper_rag_backend.env import get_env, load_env

load_env()

for key in ("HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "GOOGLE_API_KEY"):
    value = get_env(key)
    if value and not value.startswith("your-"):
        os.environ[key] = value

Settings.llm = GoogleGenAI(model=get_env("GOOGLE_LLM_MODEL", "gemini-2.5-flash"))
Settings.embed_model = GoogleGenAIEmbedding(model_name=get_env("GOOGLE_EMBED_MODEL", "gemini-embedding-001"))


def load_existing_db():
    db = chromadb.PersistentClient(path=get_env("CHROMA_DB_PATH", "./rag_core/chroma_db"))
    chroma_collection = db.get_collection("ai_paper")
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    return VectorStoreIndex.from_vector_store(vector_store=vector_store)


if __name__ == "__main__":
    try:
        index = load_existing_db()
        query_engine = index.as_query_engine(streaming=True, similarity_top_k=3)

        while True:
            user_input = input("\nYou: ")
            if user_input.lower() in ["quit", "exit"]:
                break

            print("AI: ", end="")
            response = query_engine.query(user_input)
            response.print_response_stream()
            print()
    except Exception as exc:
        print(f"Failed to load vector store: {exc}")
