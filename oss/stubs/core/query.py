from .settings import LLM
from .build_index import build_index

print("=== GH05T3: Building in-memory index with badass ingestion ===")
INDEX = build_index()
print("=== GH05T3: Index ready ===")

def ask(query: str):
    engine = INDEX.as_query_engine(llm=LLM)
    return engine.query(query)
