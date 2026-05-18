from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="GH05T3")

class ChatRequest(BaseModel):
    message: str

@app.get("/")
def root():
    return {
        "name": "GH05T3",
        "status": "online",
        "endpoints": ["/chat", "/health"]
    }

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/chat")
def chat(req: ChatRequest):
    return {
        "response": f"Echo: {req.message}",
        "mode": "lite"
    }
