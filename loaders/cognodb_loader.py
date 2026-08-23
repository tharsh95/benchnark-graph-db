"""
Loader: nodes_people.csv, nodes_titles.csv, edges_acted_in.csv -> CognoDB

Expects env vars (from .env):
  COGNODB_URI=bolt+s://xxxx.databases.cognodb.com:7687
  COGNODB_USER=cognodb
  COGNODB_PASSWORD=...

Run:
  python loaders/cognodb_loader.py
"""

import csv
import os
import time

from dotenv import load_dotenv
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, TransientError


load_dotenv()

URI = os.environ["COGNODB_URI"]
USER = os.environ["COGNODB_USER"]
PASSWORD = os.environ["COGNODB_PASSWORD"]

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
)

PEOPLE_CSV = os.path.join(DATA_DIR, "nodes_people.csv")
TITLES_CSV = os.path.join(DATA_DIR, "nodes_titles.csv")
EDGES_CSV = os.path.join(DATA_DIR, "edges_acted_in.csv")


# CognoDB free tier is a small instance.
# Keep batches small to avoid request timeouts.
BATCH_SIZE = 50

# Number of times to retry a failed batch.
MAX_RETRIES = 3


def read_csv(path):
    """Read a CSV file one row at a time."""
    with open(path, newline="", encoding="utf-8") as f:
        yield from csv.DictReader(f)


def batched(iterable, size):
    """Group rows into small batches."""
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


def run_batch(driver, query, batch):
    """
    Execute one batch.

    A fresh session is created for every attempt so that a dead
    Bolt connection is not reused.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with driver.session() as session:
                session.run(query, rows=batch).consume()

            return

        except (ServiceUnavailable, TransientError) as e:
            print(
                f"  batch failed "
                f"(attempt {attempt}/{MAX_RETRIES}): {e}"
            )

            if attempt == MAX_RETRIES:
                raise

            time.sleep(attempt)


def load_people(driver):
    """Load Person nodes from nodes_people.csv."""
    print("Loading Person nodes...")

    total = 0

    query = """
    UNWIND $rows AS row
    MERGE (p:Person {personId: row.personId})
    SET p.name = row.name
    """

    for batch in batched(read_csv(PEOPLE_CSV), BATCH_SIZE):
        run_batch(driver, query, batch)

        total += len(batch)

        if total % 10000 == 0:
            print(f"  {total} people loaded")

    print(f"  {total} people loaded (final)")

    return total


def load_titles(driver):
    """Load Title nodes from nodes_titles.csv."""
    print("Loading Title nodes...")

    total = 0

    query = """
    UNWIND $rows AS row
    MERGE (t:Title {titleId: row.titleId})
    SET t.primaryTitle = row.primaryTitle,
        t.startYear = row.startYear
    """

    for batch in batched(read_csv(TITLES_CSV), BATCH_SIZE):

        for row in batch:
            if row.get("startYear"):
                row["startYear"] = int(row["startYear"])
            else:
                row["startYear"] = None

        run_batch(driver, query, batch)

        total += len(batch)

        if total % 10000 == 0:
            print(f"  {total} titles loaded")

    print(f"  {total} titles loaded (final)")

    return total


def load_edges(driver):
    """Load ACTED_IN relationships from edges_acted_in.csv."""
    print("Loading ACTED_IN edges...")

    total = 0

    query = """
    UNWIND $rows AS row
    MATCH (p:Person {personId: row.personId})
    MATCH (t:Title {titleId: row.titleId})
    MERGE (p)-[:ACTED_IN]->(t)
    """

    for batch in batched(read_csv(EDGES_CSV), BATCH_SIZE):
        run_batch(driver, query, batch)

        total += len(batch)

        if total % 10000 == 0:
            print(f"  {total} edges loaded")

    print(f"  {total} edges loaded (final)")

    return total


def verify_counts(driver):
    """Verify the final number of nodes and relationships."""
    with driver.session() as session:

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

    print("=== CognoDB dataset loading ===")

    driver = GraphDatabase.driver(
        URI,
        auth=(USER, PASSWORD),
        max_connection_pool_size=2,
    )

    try:

        # Schema setup is not part of the ingestion timing.
        print("Preparing schema/indexes...")

        with driver.session() as session:
            create_constraints(session)

        # Start timing only for actual data loading.
        start = time.time()

        n_people = load_people(driver)
        n_titles = load_titles(driver)
        n_edges = load_edges(driver)

        elapsed = time.time() - start

        print("\nVerifying database counts...")

        db_people, db_titles, db_edges = verify_counts(driver)

        print("=" * 50)

        print(
            f"CSV rows -> "
            f"people: {n_people}, "
            f"titles: {n_titles}, "
            f"edges: {n_edges}"
        )

        print(
            f"DB counts -> "
            f"people: {db_people}, "
            f"titles: {db_titles}, "
            f"edges: {db_edges}"
        )

        print(f"Load time: {elapsed:.2f}s")

        if elapsed > 0:
            total_nodes = n_people + n_titles

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
            print("\nWARNING: DB counts don't match CSV row counts.")
            print("The load should NOT be used as a benchmark result.")
        else:
            print("\nLoad verification: PASSED")

    except Exception as e:

        print("\nFAILED during CognoDB load:")
        print(e)

        print("\nCheck the database for partial data before retrying.")

        raise

    finally:
        driver.close()


if __name__ == "__main__":
    main()