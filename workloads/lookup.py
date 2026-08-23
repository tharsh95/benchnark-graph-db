"""
Lookup workload: measures point lookup and indexed/filtered lookup latency.

Point lookup: exact match on an indexed property (Person.personId).
Indexed/filtered lookup: range filter on an indexed property (Title.startYear).

Works against any bolt-protocol platform (CognoDB, Aura, Memgraph,
self-hosted Neo4j).

Usage: python workloads/lookup.py <PLATFORM_PREFIX>
  e.g. COGNODB, AURA, MEMGRAPH, NEO4J_SELFHOSTED
"""
import csv
import os
import sys
import time

import numpy as np
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

WARMUP_RUNS = 15
ITERATIONS = 100

POINT_LOOKUP_QUERY = """
    MATCH (p:Person {personId: $personId})
    RETURN p.name AS name
"""

# Filtered/indexed lookup: titles released in a given year, using the
# startYear property (indexed via range on Title.startYear where supported)
FILTERED_LOOKUP_QUERY = """
    MATCH (t:Title)
    WHERE t.startYear = $year
    RETURN t.titleId AS id, t.primaryTitle AS title
    LIMIT 50
"""


def get_random_person_ids(driver, n=200):
    with driver.session() as session:
        result = session.run(
            "MATCH (p:Person) RETURN p.personId AS id ORDER BY rand() LIMIT $n", n=n
        )
        return [r["id"] for r in result]


def get_year_range(driver):
    with driver.session() as session:
        result = session.run(
            "MATCH (t:Title) RETURN DISTINCT t.startYear AS year"
        )
        years = [r["year"] for r in result if r["year"] is not None]
        return years


def time_query(driver, query, params):
    start = time.perf_counter()
    with driver.session() as session:
        session.run(query, **params).consume()
    return (time.perf_counter() - start) * 1000  # ms


def run_benchmark(driver, query, param_pool, param_name):
    for i in range(WARMUP_RUNS):
        val = param_pool[i % len(param_pool)]
        time_query(driver, query, {param_name: val})

    latencies = []
    for i in range(ITERATIONS):
        val = param_pool[i % len(param_pool)]
        latencies.append(time_query(driver, query, {param_name: val}))

    return latencies


def save_results(platform, label, latencies):
    p50 = np.percentile(latencies, 50)
    p95 = np.percentile(latencies, 95)
    print(f"  {label}: p50={p50:.2f}ms  p95={p95:.2f}ms")

    raw_path = f"results/lookup_{platform.lower()}_{label.replace(' ', '_')}_raw.csv"
    with open(raw_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["iteration", "latency_ms"])
        for i, lat in enumerate(latencies):
            writer.writerow([i, lat])

    return {"query": label, "p50_ms": p50, "p95_ms": p95, "n": len(latencies)}


def main():
    if len(sys.argv) != 2:
        print("Usage: python workloads/lookup.py <PLATFORM_PREFIX>")
        sys.exit(1)

    platform = sys.argv[1].upper()
    uri = os.getenv(f"{platform}_URI")
    user = os.getenv(f"{platform}_USER") or None
    password = os.getenv(f"{platform}_PASSWORD") or None

    if not uri:
        print(f"No {platform}_URI found in .env")
        sys.exit(1)

    print(f"=== Lookup benchmark: {platform} ===")
    auth = (user, password) if user else None
    driver = GraphDatabase.driver(uri, auth=auth)
    driver.verify_connectivity()

    print("Fetching random person IDs...")
    person_ids = get_random_person_ids(driver, n=200)
    if not person_ids:
        print("No Person nodes found - did you run the loader for this platform?")
        sys.exit(1)
    print(f"  got {len(person_ids)} candidate IDs")

    print("Fetching available years...")
    years = get_year_range(driver)
    if not years:
        print("No Title.startYear values found - did you run the loader?")
        sys.exit(1)
    print(f"  got {len(years)} distinct years")

    os.makedirs("results", exist_ok=True)
    summary_rows = []

    print(f"\nRunning point lookup ({WARMUP_RUNS} warmup + {ITERATIONS} timed)...")
    latencies = run_benchmark(driver, POINT_LOOKUP_QUERY, person_ids, "personId")
    summary_rows.append(save_results(platform, "point_lookup", latencies))

    print(f"\nRunning indexed/filtered lookup ({WARMUP_RUNS} warmup + {ITERATIONS} timed)...")
    latencies = run_benchmark(driver, FILTERED_LOOKUP_QUERY, years, "year")
    summary_rows.append(save_results(platform, "filtered_lookup", latencies))

    summary_path = f"results/lookup_{platform.lower()}_summary.csv"
    with open(summary_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["query", "p50_ms", "p95_ms", "n"])
        writer.writeheader()
        writer.writerows(summary_rows)

    print(f"\nSaved summary to {summary_path}")
    driver.close()


if __name__ == "__main__":
    main()
