import sqlite3
import pickle
from sentence_transformers import SentenceTransformer
import faiss

DB_PATH = "sample.db"

def get_table_descriptions(db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]

    descriptions = []
    for table in tables:
        cursor.execute(f"PRAGMA table_info({table})")
        columns = cursor.fetchall()
        column_desc = ", ".join([f"{col[1]} ({col[2]})" for col in columns])
        desc = f"Table '{table}': columns are {column_desc}"
        descriptions.append((table, desc))

    conn.close()
    return descriptions

def build_index():
    table_data = get_table_descriptions()
    model = SentenceTransformer("all-MiniLM-L6-v2")

    texts = [desc for _, desc in table_data]
    embeddings = model.encode(texts)

    index = faiss.IndexFlatL2(embeddings.shape[1])
    index.add(embeddings)

    faiss.write_index(index, "rag/schema_index.faiss")
    with open("rag/table_data.pkl", "wb") as f:
        pickle.dump(table_data, f)

    print(f"Indexed {len(table_data)} tables.")

if __name__ == "__main__":
    build_index()