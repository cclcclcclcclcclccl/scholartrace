from pathlib import Path
import sys
import pymupdf

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import store

updates = []
for item in store.list_documents():
    record = store.get_document(item["id"])
    if len(record["metadata"]["pages_without_text"]) == record["pages"]:
        continue  # Preserve OCR-derived or manually supplied scan titles.
    with pymupdf.open(record["path"]) as doc:
        title = store.document_title(doc)
    updates.append((title, item["id"]))
with store.connection() as conn:
    conn.executemany("UPDATE documents SET title=? WHERE id=?", updates)
print("Updated", len(updates), "native document titles")
