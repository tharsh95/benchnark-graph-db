"""
Loader: nodes_people.csv, nodes_titles.csv, edges_acted_in.csv -> Neo4j Aura

Expects env vars (from .env):
  AURA_URI=neo4j+s://xxxx.databases.neo4j.io
  AURA_USER=neo4j
  AURA_PASSWORD=...

Run: python loaders/neo4j_aura_loader.py
"""

import csv
import os
import time

from dotenv import load_dotenv
from neo4j import GraphDatabase


load_dotenv()

URI = os.environ["AURA_URI"]
USER = os.environ["AURA_USER"]
PASSWORD = os.environ["AURA_PASSWORD"]


DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data"
)

PEOPLE_CSV = os.path.join(DATA_DIR, "nodes_people.csv")
TITLES_CSV = os.path.join(DATA_DIR, "nodes_titles.csv")
EDGES_CSV = os.path.join(DATA_DIR, "edges_acted_in.csv")


# Aura is a cloud database, so use smaller batches
# to reduce the chance of transaction/network timeouts.
BATCH_SIZE = 1000


def read_csv(path):
    """Read a CSV file one row at a time."""
    with open(path, newline="", encoding="utf-8") as f:
        yield from csv.DictReader(f)


def batched(iterable, size):
    """Group CSV rows into batches."""
    batch = []

    for row in iterable:
        batch.append(row)

        if len(batch) >= size:
            yield batch
            batch = []

    if batch:
        yield batch


def create_constraints(session):
    """Create unique constraints for Person and Title IDs."""

    session.run(
        "CREATE CONSTRAINT person_id IF NOT EXISTS "
        "FOR (p:Person) REQUIRE p.personId IS UNIQUE"
    ).consume()

    session.run(
        "CREATE CONSTRAINT title_id IF NOT EXISTS "
        "FOR (t:Title) REQUIRE t.titleId IS UNIQUE"
    ).consume()


def load_people(session):
    """Load Person nodes from the people CSV."""

    print("Loading Person nodes...")

    total = 0

    for batch in batched(read_csv(PEOPLE_CSV), BATCH_SIZE):

        session.run(
            """
            UNWIND $rows AS row
            MERGE (p:Person {personId: row.personId})
            SET p.name = row.name
            """,
            rows=batch,
        ).consume()

        total += len(batch)

        if total % 10000 == 0:
            print(f"  {total} people loaded")

    print(f"  {total} people loaded (final)")

    return total


def load_titles(session):
    """Load Title nodes from the titles CSV."""

    print("Loading Title nodes...")

    total = 0

    for batch in batched(read_csv(TITLES_CSV), BATCH_SIZE):

        for row in batch:
            row["startYear"] = (
                int(row["startYear"])
                if row.get("startYear")
                else None
            )

        session.run(
            """
            UNWIND $rows AS row
            MERGE (t:Title {titleId: row.titleId})
            SET t.primaryTitle = row.primaryTitle,
                t.startYear = row.startYear
            """,
            rows=batch,
        ).consume()

        total += len(batch)

        if total % 10000 == 0:
            print(f"  {total} titles loaded")

    print(f"  {total} titles loaded (final)")

    return total


def load_edges(session):
    """Load ACTED_IN relationships from the edges CSV."""

    print("Loading ACTED_IN edges...")

    total = 0

    for batch in batched(read_csv(EDGES_CSV), BATCH_SIZE):

        session.run(
            """
            UNWIND $rows AS row
            MATCH (p:Person {personId: row.personId})
            MATCH (t:Title {titleId: row.titleId})
            MERGE (p)-[:ACTED_IN]->(t)
            """,
            rows=batch,
        ).consume()

        total += len(batch)

        if total % 10000 == 0:
            print(f"  {total} edges loaded")

    print(f"  {total} edges loaded (final)")

    return total


def verify_counts(session):

    people = session.run(
        "MATCH (p:Person) RETURN count(p) AS c"
    ).single()["c"]

    titles = session.run(
        "MATCH (t:Title) RETURN count(t) AS c"
    ).single()["c"]

    edges = session.run(
        "MATCH ()-[r:ACTED_IN]->() RETURN count(r) AS c"
    ).single()["c"]

    return people, titles, edges


def main():

    driver = GraphDatabase.driver(
        URI,
        auth=(USER, PASSWORD)
    )

    try:

        print("Preparing constraints...")

        with driver.session() as session:
            create_constraints(session)

        # Start measuring only the actual data loading.
        start = time.time()

        with driver.session() as session:

            n_people = load_people(session)
            n_titles = load_titles(session)
            n_edges = load_edges(session)

        # Stop the ingestion timer before verification.
        elapsed = time.time() - start

        # Verification is not part of ingestion time.
        with driver.session() as session:
            db_people, db_titles, db_edges = verify_counts(session)

    except Exception as e:

        print(f"FAILED partway through Aura load: {e}")
        raise

    finally:
        driver.close()

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