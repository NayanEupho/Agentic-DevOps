# devops_agent/data_loader.py
"""
Data Loading Utilities.
"""
import os
import json

def get_data_file(filename: str) -> str:
    """Return absolute path to a file in devops_agent/data/"""
    return os.path.join(os.path.dirname(__file__), "data", filename)

def load_intents():
    """Load intent data for router."""
    path = get_data_file("intents.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"templates": [], "semantic_examples": []}
