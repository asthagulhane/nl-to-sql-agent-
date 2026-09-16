import pickle
from sentence_transformers import SentenceTransformer
import faiss

model = SentenceTransformer("all-MiniLM-L6-v2")
index = faiss.read_index("rag/schema_index.faiss")
with open("rag/table_data.pkl", "rb") as f:
    table_data = pickle.load(f)

def get_relevant_schema(question: str, k: int = 3) -> str:
    query_vec = model.encode([question])
    distances, indices = index.search(query_vec, k)
    relevant = [table_data[i][1] for i in indices[0]]
    return "\n".join(relevant)