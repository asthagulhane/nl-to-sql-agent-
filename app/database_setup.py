import sqlite3

connection = sqlite3.connect("app/sample.db")
cursor = connection.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS employees (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    department TEXT NOT NULL,
    salary INTEGER NOT NULL
)
""")

sample_data = [
    (1, "Aisha Khan", "Engineering", 75000),
    (2, "Rohan Mehta", "Sales", 55000),
    (3, "Priya Nair", "Engineering", 82000),
    (4, "Vikram Singh", "Marketing", 60000),
    (5, "Sneha Rao", "Sales", 58000),
]

cursor.executemany(
    "INSERT OR IGNORE INTO employees (id, name, department, salary) VALUES (?, ?, ?, ?)",
    sample_data
)

connection.commit()
connection.close()

print("Database created and seeded successfully!")