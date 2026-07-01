from core.ingest import load_documents
from .obs import setup_logger, log_event

logger = setup_logger("ingestion")

def load_training_data():
    docs = load_documents()
    samples = []
    for doc in docs:
        text = doc.text.strip()
        if len(text) > 0:
            samples.append(text)

    log_event(
        logger,
        "ingestion_complete",
        total_docs=len(docs),
        usable_samples=len(samples),
    )

    return samples
