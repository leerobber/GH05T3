from llama_index.llms.ollama import Ollama
from llama_index.embeddings.ollama import OllamaEmbedding

LLM = Ollama(
    model="llama3.1:8b",
    request_timeout=120,
)

EMBED = OllamaEmbedding(
    model_name="nomic-embed-text",
)
