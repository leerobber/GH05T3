from llama_index.core import VectorStoreIndex
from .settings import EMBED
from .ingest import load_documents

def build_index():
    docs = load_documents()
    index = VectorStoreIndex.from_documents(
        docs,
        embed_model=EMBED,
    )
    return index
