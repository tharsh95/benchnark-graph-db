"""
Checks whether a Neo4j-compatible platform already has the correct
node/edge counts loaded.

Exits 0 if counts match the CSVs.
Exits 1 otherwise.

Usage: python check_loaded.py <PLATFORM_PREFIX>
"""

import os
import sys

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()


def csv_count(path):
    with open(path, newline="", encoding="utf-8") as f:
        return sum(1 for _ in f) - 1


def main():
    if len(sys.argv) != 2:
        print("Usage: python check_loaded.py <PLATFORM_PREFIX>")
        sys.exit(1)

    platform = sys.argv[1].upper()

    uri = os.getenv(f"{platform}_URI")
    user = os.getenv(f"{platform}_USER") or None
    password = os.getenv(f"{platform}_PASSWORD") or None

    if not uri:
        print(f"{platform}: NOT_LOADED (no {platform}_URI in .env)")
        sys.exit(1)

    expected_people = csv_count("data/nodes_people.csv")
    expected_titles = csv_count("data/nodes_titles.csv")
    expected_edges = csv_count("data/edges_acted_in.csv")

    driver = None

    try:
        driver = GraphDatabase.driver(
            uri,
            auth=(user, password) if user else None,
        )

        driver.verify_connectivity()

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

    except Exception as e:
        print(f"{platform}: NOT_LOADED (connection/check failed: {e})")
        sys.exit(1)

    finally:
        if driver:
            driver.close()

    if (
        people == expected_people
        and titles == expected_titles
        and edges == expected_edges
    ):
        print(
            f"{platform}: LOADED "
            f"({people} people, {titles} titles, {edges} edges)"
        )
        sys.exit(0)

    print(
        f"{platform}: NOT_LOADED "
        f"(have {people}/{titles}/{edges}, "
        f"expect {expected_people}/{expected_titles}/{expected_edges})"
    )

    sys.exit(1)


if __name__ == "__main__":
    main()