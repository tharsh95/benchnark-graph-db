"""
Checks whether ArangoDB already has the correct node/edge counts loaded.

Exits 0 if counts match the CSVs.
Exits 1 otherwise.

Usage: python check_loaded_arango.py
"""

import os
import sys

from arango import ArangoClient
from dotenv import load_dotenv

load_dotenv()


def csv_count(path):
    with open(path, newline="", encoding="utf-8") as f:
        return sum(1 for _ in f) - 1


def main():
    uri = os.getenv("ARANGO_URI")
    user = os.getenv("ARANGO_USER")
    password = os.getenv("ARANGO_PASSWORD", "")
    db_name = os.getenv("ARANGO_DB", "benchmark")

    if not uri:
        print("ARANGO: NOT_LOADED (no ARANGO_URI in .env)")
        sys.exit(1)

    expected_people = csv_count("data/nodes_people.csv")
    expected_titles = csv_count("data/nodes_titles.csv")
    expected_edges = csv_count("data/edges_acted_in.csv")

    try:
        client = ArangoClient(hosts=uri)

        db = client.db(
            db_name,
            username=user,
            password=password,
        )

        if not db.has_collection("Person"):
            print("ARANGO: NOT_LOADED (Person collection does not exist)")
            sys.exit(1)

        if not db.has_collection("Title"):
            print("ARANGO: NOT_LOADED (Title collection does not exist)")
            sys.exit(1)

        if not db.has_collection("ACTED_IN"):
            print("ARANGO: NOT_LOADED (ACTED_IN collection does not exist)")
            sys.exit(1)

        people = db.collection("Person").count()
        titles = db.collection("Title").count()
        edges = db.collection("ACTED_IN").count()

    except Exception as e:
        print(f"ARANGO: NOT_LOADED (connection/check failed: {e})")
        sys.exit(1)

    if (
        people == expected_people
        and titles == expected_titles
        and edges == expected_edges
    ):
        print(
            f"ARANGO: LOADED "
            f"({people} people, {titles} titles, {edges} edges)"
        )
        sys.exit(0)

    print(
        f"ARANGO: NOT_LOADED "
        f"(have {people}/{titles}/{edges}, "
        f"expect {expected_people}/{expected_titles}/{expected_edges})"
    )

    sys.exit(1)


if __name__ == "__main__":
    main()