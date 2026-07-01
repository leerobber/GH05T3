from llama_index.llms.ollama import Ollama
from llama_index.embeddings.ollama import OllamaEmbedding

llm = Ollama(model="llama3.1:8b")
embed = OllamaEmbedding(model_name="nomic-embed-text")

print("LLM OK:", llm)
print("Embedding OK:", embed)
