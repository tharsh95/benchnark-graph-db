"""
Loader: nodes_people.csv, nodes_titles.csv, edges_acted_in.csv -> ArangoDB

Expects env vars (from .env):
  ARANGO_URI=http://localhost:8529
  ARANGO_USER=root
  ARANGO_PASSWORD=
  ARANGO_DB=benchmark

Run: python loaders/arango_loader.py
"""

import csv
import os
import time

from dotenv import load_dotenv
from arango import ArangoClient


load_dotenv()

URI = os.environ["ARANGO_URI"]
USER = os.environ["ARANGO_USER"]
PASSWORD = os.environ.get("ARANGO_PASSWORD", "")
DB_NAME = os.environ["ARANGO_DB"]


DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data"
)

PEOPLE_CSV = os.path.join(DATA_DIR, "nodes_people.csv")
TITLES_CSV = os.path.join(DATA_DIR, "nodes_titles.csv")
EDGES_CSV = os.path.join(DATA_DIR, "edges_acted_in.csv")


# Small capped instance.
BATCH_SIZE = 500


PEOPLE_COLL = "Person"
TITLES_COLL = "Title"
EDGES_COLL = "ACTED_IN"


def read_csv(path):
    """Read CSV rows one at a time."""

    with open(path, newline="", encoding="utf-8") as f:
        yield from csv.DictReader(f)


def batched(iterable, size):
    """Group rows into batches."""

    batch = []

    for row in iterable:

        batch.append(row)

        if len(batch) >= size:
            yield batch
            batch = []

    if batch:
        yield batch


def get_db():
    """Connect to ArangoDB and create the benchmark database if needed."""

    client = ArangoClient(hosts=URI)

    sys_db = client.db(
        "_system",
        username=USER,
        password=PASSWORD
    )

    if not sys_db.has_database(DB_NAME):
        sys_db.create_database(DB_NAME)

    return client.db(
        DB_NAME,
        username=USER,
        password=PASSWORD
    )


def ensure_collections(db):
    """Create node and edge collections and required indexes."""

    if not db.has_collection(PEOPLE_COLL):
        people = db.create_collection(PEOPLE_COLL)
    else:
        people = db.collection(PEOPLE_COLL)

    people.add_persistent_index(
        fields=["personId"],
        unique=True,
        sparse=False
    )

    if not db.has_collection(TITLES_COLL):
        titles = db.create_collection(TITLES_COLL)
    else:
        titles = db.collection(TITLES_COLL)

    titles.add_persistent_index(
        fields=["titleId"],
        unique=True,
        sparse=False
    )

    if not db.has_collection(EDGES_COLL):
        db.create_collection(
            EDGES_COLL,
            edge=True
        )


def load_people(db):
    """Load Person documents."""

    print("Loading Person documents...")

    coll = db.collection(PEOPLE_COLL)

    total = 0

    for batch in batched(
        read_csv(PEOPLE_CSV),
        BATCH_SIZE
    ):

        docs = [
            {
                "_key": row["personId"],
                "personId": row["personId"],
                "name": row["name"]
            }
            for row in batch
        ]

        coll.insert_many(
            docs,
            overwrite=True,
            silent=True
        )

        total += len(batch)

        if total % 10000 == 0:
            print(f"  {total} people loaded")

    print(f"  {total} people loaded (final)")

    return total


def load_titles(db):
    """Load Title documents."""

    print("Loading Title documents...")

    coll = db.collection(TITLES_COLL)

    total = 0

    for batch in batched(
        read_csv(TITLES_CSV),
        BATCH_SIZE
    ):

        docs = []

        for row in batch:

            start_year = (
                int(row["startYear"])
                if row.get("startYear")
                else None
            )

            docs.append(
                {
                    "_key": row["titleId"],
                    "titleId": row["titleId"],
                    "primaryTitle": row["primaryTitle"],
                    "startYear": start_year
                }
            )

        coll.insert_many(
            docs,
            overwrite=True,
            silent=True
        )

        total += len(batch)

        if total % 10000 == 0:
            print(f"  {total} titles loaded")

    print(f"  {total} titles loaded (final)")

    return total


def load_edges(db):
    """Load ACTED_IN edge documents."""

    print("Loading ACTED_IN edges...")

    coll = db.collection(EDGES_COLL)

    total = 0

    for batch in batched(
        read_csv(EDGES_CSV),
        BATCH_SIZE
    ):

        docs = []

        for row in batch:

            person_id = row["personId"]
            title_id = row["titleId"]

            docs.append(
                {
                    "_key": f"{person_id}_{title_id}",
                    "_from": f"{PEOPLE_COLL}/{person_id}",
                    "_to": f"{TITLES_COLL}/{title_id}"
                }
            )

        coll.insert_many(
            docs,
            overwrite=True,
            silent=True
        )

        total += len(batch)

        if total % 10000 == 0:
            print(f"  {total} edges loaded")

    print(f"  {total} edges loaded (final)")

    return total


def verify_counts(db):

    people = db.collection(
        PEOPLE_COLL
    ).count()

    titles = db.collection(
        TITLES_COLL
    ).count()

    edges = db.collection(
        EDGES_COLL
    ).count()

    return people, titles, edges


def main():

    db = get_db()

    try:

        print("Preparing collections and indexes...")

        ensure_collections(db)

        # Start timing only after setup.
        start = time.time()

        n_people = load_people(db)
        n_titles = load_titles(db)
        n_edges = load_edges(db)

        elapsed = time.time() - start

        # Verification is outside the load timer.
        db_people, db_titles, db_edges = verify_counts(db)

    except Exception as e:

        print(f"FAILED partway through load: {e}")

        print(
            "Check ArangoDB RAM/disk usage and "
            "the counts of the three collections."
        )

        raise

    total_nodes = n_people + n_titles

    print("=" * 50)

    print(
        f"CSV rows   -> "
        f"people: {n_people}, "
        f"titles: {n_titles}, "
        f"edges: {n_edges}"
    )

    print(
        f"DB counts  -> "
        f"people: {db_people}, "
        f"titles: {db_titles}, "
        f"edges: {db_edges}"
    )

    print(f"Load time: {elapsed:.2f}s")

    if elapsed > 0:

        print(
            f"Node throughput: "
            f"{total_nodes / elapsed:.2f} nodes/sec"
        )

        print(
            f"Relationship throughput: "
            f"{n_edges / elapsed:.2f} relationships/sec"
        )

    if (
        db_people != n_people
        or db_titles != n_titles
        or db_edges != n_edges
    ):
        print(
            "WARNING: DB counts don't match CSV row counts."
        )
    else:
        print("Load verification: PASSED")


if __name__ == "__main__":
    main()