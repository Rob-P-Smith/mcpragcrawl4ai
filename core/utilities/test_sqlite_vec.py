import sqlite3
import sqlite_vec
import os
import numpy as np

def load_sqlite_vec(db):
    """Helper function to load sqlite-vec extension"""
    package_dir = os.path.dirname(sqlite_vec.__file__)
    extension_path = os.path.join(package_dir, 'vec0.so')
    db.enable_load_extension(True)
    db.load_extension(extension_path)
    return db

def test_vector_operations():
    db = sqlite3.connect(':memory:')
    load_sqlite_vec(db)

    db.execute('''
        CREATE VIRTUAL TABLE docs USING vec0(
            embedding FLOAT[384]
        )
    ''')

    test_vectors = [
        np.random.rand(384).astype(np.float32),
        np.random.rand(384).astype(np.float32),
        np.random.rand(384).astype(np.float32)
    ]

    for i, vector in enumerate(test_vectors):
        vector_bytes = vector.tobytes()
        db.execute('INSERT INTO docs(rowid, embedding) VALUES (?, ?)', (i, vector_bytes))

    query_vector = np.random.rand(384).astype(np.float32)
    query_bytes = query_vector.tobytes()

    results = db.execute('''
        SELECT rowid, distance
        FROM docs
        WHERE embedding MATCH ?
        ORDER BY distance
        LIMIT 2
    ''', [query_bytes]).fetchall()

    print("Vector search results:", results)
    print("Test successful!")

    db.close()

if __name__ == "__main__":
    test_vector_operations()
