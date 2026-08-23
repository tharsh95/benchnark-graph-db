"""
Traversal workload for ArangoDB: measures 1-hop, 2-hop, 3-hop query latency
using AQL graph traversal syntax. Mirrors workloads/traversal.py so results
are directly comparable, but ArangoDB needs its own driver (python-arango,
HTTP-based) since it doesn't speak Cypher/bolt.

Usage: python workloads/traversal_arango.py
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

QUERIES = {
    1: """
        FOR t IN 1..1 OUTBOUND CONCAT('Person/', @startId) ACTED_IN
            LIMIT 50
            RETURN t._key
    """,
    2: """
        FOR v, e, p IN 2..2 ANY CONCAT('Person/', @startId) ACTED_IN
            FILTER IS_SAME_COLLECTION('Person', v)
            LIMIT 50
            RETURN DISTINCT v._key
    """,
    3: """
        FOR v, e, p IN 3..3 ANY CONCAT('Person/', @startId) ACTED_IN
            FILTER IS_SAME_COLLECTION('Title', v)
            LIMIT 50
            RETURN DISTINCT v._key
    """,
}


def get_random_person_ids(db, n=200):
    cursor = db.aql.execute(
        f"FOR p IN Person LIMIT {n} RETURN p.personId"
    )
    return list(cursor)


def time_query(db, query, bind_vars):
    start = time.perf_counter()
    cursor = db.aql.execute(query, bind_vars=bind_vars)
    list(cursor)  # force full consumption, same as .consume() on the bolt side
    return (time.perf_counter() - start) * 1000  # ms


def run_hop_benchmark(db, hop, start_ids):
    query = QUERIES[hop]

    for i in range(WARMUP_RUNS):
        sid = start_ids[i % len(start_ids)]
        time_query(db, query, {"startId": sid})

    latencies = []
    for i in range(ITERATIONS):
        sid = start_ids[i % len(start_ids)]
        latencies.append(time_query(db, query, {"startId": sid}))

    return latencies


def main():
    uri = os.getenv("ARANGO_URI")
    user = os.getenv("ARANGO_USER")
    password = os.getenv("ARANGO_PASSWORD")
    db_name = os.getenv("ARANGO_DB", "benchmark")

    print("=== Traversal benchmark: ARANGO ===")
    client = ArangoClient(hosts=uri)
    db = client.db(db_name, username=user, password=password)

    print("Fetching random start node pool...")
    start_ids = get_random_person_ids(db, n=200)
    if not start_ids:
        print("No people found - did you run the ArangoDB loader?")
        return
    print(f"  got {len(start_ids)} candidate start nodes")

    os.makedirs("results", exist_ok=True)
    summary_rows = []

    for hop in (1, 2, 3):
        print(f"\nRunning {hop}-hop traversal ({WARMUP_RUNS} warmup + {ITERATIONS} timed)...")
        latencies = run_hop_benchmark(db, hop, start_ids)

        p50 = np.percentile(latencies, 50)
        p95 = np.percentile(latencies, 95)
        print(f"  {hop}-hop: p50={p50:.2f}ms  p95={p95:.2f}ms")

        raw_path = f"results/traversal_arango_{hop}hop_raw.csv"
        with open(raw_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["iteration", "latency_ms"])
            for i, lat in enumerate(latencies):
                writer.writerow([i, lat])

        summary_rows.append({"hop": hop, "p50_ms": p50, "p95_ms": p95, "n": len(latencies)})

    summary_path = "results/traversal_arango_summary.csv"
    with open(summary_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["hop", "p50_ms", "p95_ms", "n"])
        writer.writeheader()
        writer.writerows(summary_rows)

    print(f"\nSaved summary to {summary_path}")


if __name__ == "__main__":
    main()