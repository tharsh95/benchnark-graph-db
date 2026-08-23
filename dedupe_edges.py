"""
Dedupes data/edges_acted_in.csv so every platform loads an identical,
unique set of (personId, titleId) edges regardless of how each loader's
write semantics (MERGE vs CREATE vs insert_many) handle duplicates.

Run this once, then wipe + reload all 5 platforms with the corrected file.

Usage: python dedupe_edges.py
"""
import csv
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
EDGES_CSV = os.path.join(DATA_DIR, "edges_acted_in.csv")


def main():
    if not os.path.exists(EDGES_CSV):
        print(f"ERROR: {EDGES_CSV} not found.")
        return

    seen = set()
    unique_rows = []

    with open(EDGES_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (row["personId"], row["titleId"])
            if key not in seen:
                seen.add(key)
                unique_rows.append(row)

    total_before = len(seen) + (0)  # placeholder, recompute below properly
    with open(EDGES_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        total_before = sum(1 for _ in reader)

    duplicates_removed = total_before - len(unique_rows)

    with open(EDGES_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["personId", "titleId"])
        for row in unique_rows:
            writer.writerow([row["personId"], row["titleId"]])

    print(f"Before: {total_before} rows")
    print(f"After:  {len(unique_rows)} unique rows")
    print(f"Removed {duplicates_removed} duplicate (personId, titleId) pairs")
    print(f"\nWrote deduped edges to {EDGES_CSV}")


if __name__ == "__main__":
    main()
