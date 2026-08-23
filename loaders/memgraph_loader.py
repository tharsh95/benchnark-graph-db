"""
Loader: nodes_people.csv, nodes_titles.csv, edges_acted_in.csv -> Memgraph

Expects env vars (from .env):
  MEMGRAPH_URI=bolt://localhost:7687
  MEMGRAPH_USER=
  MEMGRAPH_PASSWORD=

Run: python loaders/memgraph_loader.py
"""

import csv
import os
import time

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

URI = os.environ["MEMGRAPH_URI"]
USER = os.environ.get("MEMGRAPH_USER", "")
PASSWORD = os.environ.get("MEMGRAPH_PASSWORD", "")

AUTH = (USER, PASSWORD) if USER else None

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data"
)

PEOPLE_CSV = os.path.join(DATA_DIR, "nodes_people.csv")
TITLES_CSV = os.path.join(DATA_DIR, "nodes_titles.csv")
EDGES_CSV = os.path.join(DATA_DIR, "edges_acted_in.csv")

NODE_BATCH_SIZE = 1000
EDGE_BATCH_SIZE = 250

def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        yield from csv.DictReader(f)


def batched(iterable, size):
    batch = []

    for row in iterable:
        batch.append(row)

        if len(batch) >= size:
            yield batch
            batch = []

    if batch:
        yield batch


def create_constraints(session):

    session.run(
        "CREATE CONSTRAINT ON (p:Person) "
        "ASSERT p.personId IS UNIQUE"
    ).consume()

    session.run(
        "CREATE CONSTRAINT ON (t:Title) "
        "ASSERT t.titleId IS UNIQUE"
    ).consume()


def load_people(session):

    print("Loading Person nodes...")

    total = 0

    for batch in batched(read_csv(PEOPLE_CSV), NODE_BATCH_SIZE):

        session.run(
            """
            UNWIND $rows AS row
            CREATE (p:Person {personId: row.personId})
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

    print("Loading Title nodes...")

    total = 0

    for batch in batched(read_csv(TITLES_CSV), NODE_BATCH_SIZE):

        for row in batch:
            row["startYear"] = (
                int(row["startYear"])
                if row.get("startYear")
                else None
            )

        session.run(
            """
            UNWIND $rows AS row
            CREATE (t:Title {titleId: row.titleId})
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

    print("Loading ACTED_IN edges...")

    total = 0

    for batch in batched(read_csv(EDGES_CSV), EDGE_BATCH_SIZE):

        session.run(
            """
            UNWIND $rows AS row
            MATCH (p:Person {personId: row.personId})
            MATCH (t:Title {titleId: row.titleId})
            CREATE (p)-[:ACTED_IN]->(t)
            """,
            rows=batch,
        )

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
        auth=AUTH
    )

    try:

        with driver.session() as session:

            print("Preparing constraints...")

            create_constraints(session)

            start = time.time()

            n_people = load_people(session)
            n_titles = load_titles(session)
            n_edges = load_edges(session)

            elapsed = time.time() - start

            db_people, db_titles, db_edges = verify_counts(session)

    except Exception as e:

        print(f"FAILED partway through load: {e}")

        print(
            "Likely cause: Memgraph RAM limit or database error."
        )

        raise

    finally:
        driver.close()

    total_nodes = n_people + n_titles

    print("=" * 50)

    print(
        f"CSV rows   -> people: {n_people}, "
        f"titles: {n_titles}, edges: {n_edges}"
    )

    print(
        f"DB counts  -> people: {db_people}, "
        f"titles: {db_titles}, edges: {db_edges}"
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
        print("WARNING: DB counts don't match CSV row counts.")

    else:
        print("Load verification: PASSED")


if __name__ == "__main__":
    main()