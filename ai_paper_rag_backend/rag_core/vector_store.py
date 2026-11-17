import os
import time as sys_time

import chromadb
from llama_index.core import Settings, StorageContext, VectorStoreIndex
from llama_index.embeddings.google_genai import GoogleGenAIEmbedding
from llama_index.llms.google_genai import GoogleGenAI
from llama_index.vector_stores.chroma import ChromaVectorStore

from ai_paper_rag_backend.env import get_env, load_env
from rag_core.data_ingestion import chunk_document, parse_ai_paper

load_env()

for key in ("HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "GOOGLE_API_KEY"):
    value = get_env(key)
    if value and not value.startswith("your-"):
        os.environ[key] = value

Settings.llm = GoogleGenAI(model=get_env("GOOGLE_LLM_MODEL", "gemini-2.5-flash"))
Settings.embed_model = GoogleGenAIEmbedding(model_name=get_env("GOOGLE_EMBED_MODEL", "gemini-embedding-001"))


def build_vector_index(nodes):
    db = chromadb.PersistentClient(path=get_env("CHROMA_DB_PATH", "./rag_core/chroma_db"))

    try:
        db.delete_collection("ai_paper")
    except Exception:
        pass

    chroma_collection = db.get_or_create_collection("ai_paper")
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    batch_size = 10
    index = VectorStoreIndex(nodes[:batch_size], storage_context=storage_context)

    for i in range(batch_size, len(nodes), batch_size):
        sys_time.sleep(15)
        batch = nodes[i:i + batch_size]
        index.insert_nodes(batch)

    return index


if __name__ == "__main__":
    pdf_path = "./stable_diffusion.pdf"

    if os.path.exists(pdf_path):
        docs = parse_ai_paper(pdf_path)
        nodes = chunk_document(docs)
        index = build_vector_index(nodes)
        query_engine = index.as_query_engine(streaming=True, similarity_top_k=3)

        while True:
            user_input = input("\nYou: ")
            if user_input.lower() in ["quit", "exit"]:
                break

            print("AI: ", end="")
            response = query_engine.query(user_input)
            response.print_response_stream()
            print()
    else:
        print("PDF file not found.")
