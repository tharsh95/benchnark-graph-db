"""
Lookup workload for ArangoDB: point lookup + indexed/filtered lookup.
Mirrors workloads/lookup.py so results are directly comparable.

Usage: python workloads/lookup_arango.py
"""
import csv
import os
import time

import numpy as np
from arango import ArangoClient
from dotenv import load_dotenv

load_dotenv()

WARMUP_RUNS = 15
ITERATIONS = 100

POINT_LOOKUP_QUERY = """
    FOR p IN Person
        FILTER p.personId == @personId
        RETURN p.name
"""

FILTERED_LOOKUP_QUERY = """
    FOR t IN Title
        FILTER t.startYear == @year
        LIMIT 50
        RETURN {id: t.titleId, title: t.primaryTitle}
"""


def get_random_person_ids(db, n=200):
    cursor = db.aql.execute(f"FOR p IN Person LIMIT {n} RETURN p.personId")
    return list(cursor)


def get_year_range(db):
    cursor = db.aql.execute(
        "FOR t IN Title FILTER t.startYear != null RETURN DISTINCT t.startYear"
    )
    return list(cursor)


def time_query(db, query, bind_vars):
    start = time.perf_counter()
    cursor = db.aql.execute(query, bind_vars=bind_vars)
    list(cursor)
    return (time.perf_counter() - start) * 1000


def run_benchmark(db, query, param_pool, param_name):
    for i in range(WARMUP_RUNS):
        val = param_pool[i % len(param_pool)]
        time_query(db, query, {param_name: val})

    latencies = []
    for i in range(ITERATIONS):
        val = param_pool[i % len(param_pool)]
        latencies.append(time_query(db, query, {param_name: val}))

    return latencies


def save_results(label, latencies):
    p50 = np.percentile(latencies, 50)
    p95 = np.percentile(latencies, 95)
    print(f"  {label}: p50={p50:.2f}ms  p95={p95:.2f}ms")

    raw_path = f"results/lookup_arango_{label}_raw.csv"
    with open(raw_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["iteration", "latency_ms"])
        for i, lat in enumerate(latencies):
            writer.writerow([i, lat])

    return {"query": label, "p50_ms": p50, "p95_ms": p95, "n": len(latencies)}


def main():
    uri = os.getenv("ARANGO_URI")
    user = os.getenv("ARANGO_USER")
    password = os.getenv("ARANGO_PASSWORD")
    db_name = os.getenv("ARANGO_DB", "benchmark")

    print("=== Lookup benchmark: ARANGO ===")
    client = ArangoClient(hosts=uri)
    db = client.db(db_name, username=user, password=password)

    print("Fetching random person IDs...")
    person_ids = get_random_person_ids(db, n=200)
    if not person_ids:
        print("No people found - did you run the ArangoDB loader?")
        return
    print(f"  got {len(person_ids)} candidate IDs")

    print("Fetching available years...")
    years = get_year_range(db)
    if not years:
        print("No Title.startYear values found - did you run the loader?")
        return
    print(f"  got {len(years)} distinct years")

    os.makedirs("results", exist_ok=True)
    summary_rows = []

    print(f"\nRunning point lookup ({WARMUP_RUNS} warmup + {ITERATIONS} timed)...")
    latencies = run_benchmark(db, POINT_LOOKUP_QUERY, person_ids, "personId")
    summary_rows.append(save_results("point_lookup", latencies))

    print(f"\nRunning indexed/filtered lookup ({WARMUP_RUNS} warmup + {ITERATIONS} timed)...")
    latencies = run_benchmark(db, FILTERED_LOOKUP_QUERY, years, "year")
    summary_rows.append(save_results("filtered_lookup", latencies))

    summary_path = "results/lookup_arango_summary.csv"
    with open(summary_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["query", "p50_ms", "p95_ms", "n"])
        writer.writeheader()
        writer.writerows(summary_rows)

    print(f"\nSaved summary to {summary_path}")


if __name__ == "__main__":
    main()
