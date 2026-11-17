from ai_paper_rag_backend.env import get_env, load_env
from llama_index.core.node_parser import MarkdownNodeParser
from llama_parse import LlamaParse

load_env()


def parse_ai_paper(pdf_path):
    parser = LlamaParse(
        api_key=get_env("LLAMA_PARSE_API_KEY"),
        result_type="markdown",
        verbose=True,
        language="en",
    )
    return parser.load_data(pdf_path)



def chunk_document(documents):
    node_parser = MarkdownNodeParser()
    return node_parser.get_nodes_from_documents(documents)
