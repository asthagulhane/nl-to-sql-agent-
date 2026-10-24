"""Lazy-loaded schema retrieval so API import and offline tests do not download models."""
import os
import pickle
from functools import lru_cache

import faiss
from sentence_transformers import SentenceTransformer

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


@lru_cache(maxsize=1)
def _load_retriever():
    """Load the embedding model and local FAISS artifacts on first retrieval."""
    model_name = os.getenv("QUERYMIND_EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    model = SentenceTransformer(model_name)
    index_path = os.path.join(BASE_DIR, "schema_index.faiss")
    data_path = os.path.join(BASE_DIR, "table_data.pkl")
    index = faiss.read_index(index_path)
    with open(data_path, "rb") as handle:
        table_data = pickle.load(handle)
    return model, index, table_data


def get_relevant_schema(question: str, k: int = 3) -> str:
    model, index, table_data = _load_retriever()
    query_vec = model.encode([question])
    distances, indices = index.search(query_vec, k)
    relevant = [table_data[i][1] for i in indices[0] if 0 <= i < len(table_data)]
    return "\n".join(relevant)
