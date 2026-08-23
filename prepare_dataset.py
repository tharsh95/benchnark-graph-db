"""
Downloads IMDb non-commercial datasets and builds a movie-actor graph
suitable for the benchmark: ~150k-200k ACTED_IN relationships.

Output files (in ./data/):
  nodes_people.csv   -> personId, name
  nodes_titles.csv   -> titleId, primaryTitle, startYear
  edges_acted_in.csv -> personId, titleId

Source: https://datasets.imdbws.com/ (IMDb Non-Commercial Datasets)

Run: python prepare_dataset.py
"""

import csv
import gzip
import os
import shutil
import sys
import urllib.request


DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
RAW_DIR = os.path.join(DATA_DIR, "raw")

IMDB_BASE = "https://datasets.imdbws.com/"
FILES = [
    "title.basics.tsv.gz",
    "title.principals.tsv.gz",
    "name.basics.tsv.gz",
]

# Filters to keep the graph within the 100k-500k relationship range
MIN_YEAR = 2015
MAX_TITLES = 50000
TARGET_EDGES = 180000


def download_files():
    """Download the required IMDb datasets if they are not already present."""
    os.makedirs(RAW_DIR, exist_ok=True)

    for fname in FILES:
        dest = os.path.join(RAW_DIR, fname)

        if os.path.exists(dest):
            print(f"  already downloaded: {fname}")
            continue

        url = IMDB_BASE + fname
        print(f"  downloading {url} ...")

        try:
            with urllib.request.urlopen(url) as response, open(dest, "wb") as out:
                shutil.copyfileobj(response, out)
        except Exception:
            # Remove a partially downloaded file so the next run
            # does not mistake it for a complete dataset.
            if os.path.exists(dest):
                os.remove(dest)
            raise

        print(f"  done: {fname}")


def select_titles():
    """Pick a bounded set of movie titleIds released after MIN_YEAR."""
    print("Selecting titles...")

    path = os.path.join(RAW_DIR, "title.basics.tsv.gz")
    titles = {}

    with gzip.open(path, "rt", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")

        for row in reader:
            if row["titleType"] != "movie":
                continue

            year = row["startYear"]

            if year == "\\N" or not year.isdigit():
                continue

            if int(year) < MIN_YEAR:
                continue

            titles[row["tconst"]] = (
                row["primaryTitle"],
                year,
            )

            if len(titles) >= MAX_TITLES:
                break

    print(f"  selected {len(titles)} titles (movies, {MIN_YEAR}+)")
    return titles


def select_edges_and_people(titles):
    """
    Stream title.principals to find ACTED_IN edges for our title set,
    stopping once we reach TARGET_EDGES.

    Also collect the unique person IDs used by those relationships.
    """
    print("Selecting ACTED_IN edges...")

    path = os.path.join(RAW_DIR, "title.principals.tsv.gz")

    edges = []
    people_ids = set()

    with gzip.open(path, "rt", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")

        for row in reader:
            if row["tconst"] not in titles:
                continue

            if row["category"] not in ("actor", "actress"):
                continue

            edges.append((row["nconst"], row["tconst"]))
            people_ids.add(row["nconst"])

            if len(edges) >= TARGET_EDGES:
                break

    print(
        f"  selected {len(edges)} ACTED_IN edges, "
        f"{len(people_ids)} unique people"
    )

    return edges, people_ids


def select_people_names(people_ids):
    """Stream name.basics to resolve names for the people we need."""
    print("Resolving person names...")

    path = os.path.join(RAW_DIR, "name.basics.tsv.gz")
    people = {}

    with gzip.open(path, "rt", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")

        for row in reader:
            if row["nconst"] not in people_ids:
                continue

            people[row["nconst"]] = row["primaryName"]

            if len(people) == len(people_ids):
                break

    print(f"  resolved {len(people)}/{len(people_ids)} names")

    if len(people) != len(people_ids):
        missing = len(people_ids) - len(people)
        raise RuntimeError(
            f"Could not resolve {missing} person IDs from name.basics.tsv.gz"
        )

    return people


def write_outputs(titles, edges, people, people_ids_used):
    """Write the final benchmark CSV files."""
    os.makedirs(DATA_DIR, exist_ok=True)

    # Only write titles actually referenced by an edge.
    used_title_ids = {title_id for _, title_id in edges}

    titles_path = os.path.join(DATA_DIR, "nodes_titles.csv")
    people_path = os.path.join(DATA_DIR, "nodes_people.csv")
    edges_path = os.path.join(DATA_DIR, "edges_acted_in.csv")

    # Write titles in deterministic order.
    with open(
        titles_path,
        "w",
        newline="",
        encoding="utf-8",
    ) as f:
        writer = csv.writer(f)
        writer.writerow(["titleId", "primaryTitle", "startYear"])

        for tid in sorted(used_title_ids):
            name, year = titles[tid]
            writer.writerow([tid, name, year])

    # Write people in deterministic order.
    with open(
        people_path,
        "w",
        newline="",
        encoding="utf-8",
    ) as f:
        writer = csv.writer(f)
        writer.writerow(["personId", "name"])

        for pid in sorted(people_ids_used):
            writer.writerow([pid, people[pid]])

    # Write relationships in deterministic order.
    with open(
        edges_path,
        "w",
        newline="",
        encoding="utf-8",
    ) as f:
        writer = csv.writer(f)
        writer.writerow(["personId", "titleId"])

        for pid, tid in edges:
            writer.writerow([pid, tid])

    print(f"\nWrote to {DATA_DIR}/:")
    print(f"  nodes_titles.csv  : {len(used_title_ids)} rows")
    print(f"  nodes_people.csv  : {len(people_ids_used)} rows")
    print(f"  edges_acted_in.csv: {len(edges)} rows")

    # Basic validation.
    if len(edges) != TARGET_EDGES:
        raise RuntimeError(
            f"Expected {TARGET_EDGES} edges, but generated {len(edges)}"
        )

    if len(used_title_ids) == 0:
        raise RuntimeError("No title nodes were generated.")

    if len(people_ids_used) == 0:
        raise RuntimeError("No person nodes were generated.")


def main():
    print("=== IMDb dataset preparation ===\n")

    print("Step 1: Download raw files")
    download_files()

    print("\nStep 2: Select titles")
    titles = select_titles()

    if not titles:
        print("No titles found - aborting.")
        sys.exit(1)

    print("\nStep 3: Select edges + people")
    edges, people_ids = select_edges_and_people(titles)

    if not edges:
        print("No edges found - aborting.")
        sys.exit(1)

    print("\nStep 4: Resolve person names")
    people = select_people_names(people_ids)

    print("\nStep 5: Write output CSVs")
    write_outputs(
        titles,
        edges,
        people,
        people_ids,
    )

    print("\nDone. Dataset ready for loaders.")


if __name__ == "__main__":
    main()