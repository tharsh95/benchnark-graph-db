"""
Aggregation workload for ArangoDB: count of ACTED_IN edges grouped by
Title.startYear. Mirrors workloads/aggregation.py so results are directly
comparable.

Usage: python workloads/aggregation_arango.py
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

AGGREGATION_QUERY = """
    FOR e IN ACTED_IN
        LET t = DOCUMENT(e._to)
        COLLECT year = t.startYear WITH COUNT INTO acted_in_count
        SORT year
        RETURN {year: year, acted_in_count: acted_in_count}
"""


def time_query(db, query):
    start = time.perf_counter()
    cursor = db.aql.execute(query)
    list(cursor)
    return (time.perf_counter() - start) * 1000


def run_benchmark(db, query):
    for _ in range(WARMUP_RUNS):
        time_query(db, query)

    latencies = []
    for _ in range(ITERATIONS):
        latencies.append(time_query(db, query))

    return latencies


def main():
    uri = os.getenv("ARANGO_URI")
    user = os.getenv("ARANGO_USER")
    password = os.getenv("ARANGO_PASSWORD")
    db_name = os.getenv("ARANGO_DB", "benchmark")

    print("=== Aggregation benchmark: ARANGO ===")
    client = ArangoClient(hosts=uri)
    db = client.db(db_name, username=user, password=password)

    os.makedirs("results", exist_ok=True)

    print(f"\nRunning count/group-by aggregation ({WARMUP_RUNS} warmup + {ITERATIONS} timed)...")
    latencies = run_benchmark(db, AGGREGATION_QUERY)

    p50 = np.percentile(latencies, 50)
    p95 = np.percentile(latencies, 95)
    print(f"  aggregation: p50={p50:.2f}ms  p95={p95:.2f}ms")

    raw_path = "results/aggregation_arango_raw.csv"
    with open(raw_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["iteration", "latency_ms"])
        for i, lat in enumerate(latencies):
            writer.writerow([i, lat])

    summary_path = "results/aggregation_arango_summary.csv"
    with open(summary_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["query", "p50_ms", "p95_ms", "n"])
        writer.writeheader()
        writer.writerow({"query": "count_group_by_year", "p50_ms": p50, "p95_ms": p95, "n": len(latencies)})

    print(f"\nSaved summary to {summary_path}")


if __name__ == "__main__":
    main()
