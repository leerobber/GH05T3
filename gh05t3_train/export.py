# gh05t3_train/export.py

import torch
from .config import MODEL_NAME, CHECKPOINT_DIR

def export_model(model):
    export_path = f"{CHECKPOINT_DIR}/{MODEL_NAME}-final.pt"
    torch.save(model.state_dict(), export_path)
    print(f"Model exported to {export_path}")
