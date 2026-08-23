"""
Mixed concurrent workload: sustained queries/second under concurrent load.

Read/write mix: 80% reads (point lookup by personId), 20% writes
(create a new Person node - simulates realistic mixed traffic).

Sweeps concurrency levels (default: 10, 40 clients) using a thread pool,
each client hammering queries for a fixed duration.

Works against any bolt-protocol platform (CognoDB, Aura, Memgraph,
self-hosted Neo4j).

Usage: python workloads/mixed_concurrent.py <PLATFORM_PREFIX>
  e.g. COGNODB, AURA, MEMGRAPH, NEO4J_SELFHOSTED
"""
import csv
import os
import random
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

CONCURRENCY_LEVELS = [10, 40]
DURATION_SECONDS = 15  # per concurrency level
READ_WRITE_RATIO = 0.8  # 80% reads, 20% writes

READ_QUERY = """
    MATCH (p:Person {personId: $personId})
    RETURN p.name AS name
"""

WRITE_QUERY = """
    CREATE (p:Person {personId: $personId, name: $name})
"""


def get_random_person_ids(driver, n=500):
    with driver.session() as session:
        result = session.run(
            "MATCH (p:Person) RETURN p.personId AS id ORDER BY rand() LIMIT $n", n=n
        )
        return [r["id"] for r in result]


def worker(driver, person_ids, stop_event, counters, lock, worker_id):
    """Runs queries in a loop until stop_event is set. Thread-safe counting."""
    local_ops = 0
    local_errors = 0
    write_counter = 0

    while not stop_event.is_set():
        try:
            is_write = random.random() > READ_WRITE_RATIO
            with driver.session() as session:
                if is_write:
                    write_counter += 1
                    synthetic_id = f"bench_{worker_id}_{write_counter}"
                    session.run(
                        WRITE_QUERY, personId=synthetic_id, name="Benchmark Synthetic"
                    ).consume()
                else:
                    pid = random.choice(person_ids)
                    session.run(READ_QUERY, personId=pid).consume()
            local_ops += 1
        except Exception:
            local_errors += 1

    with lock:
        counters["ops"] += local_ops
        counters["errors"] += local_errors


def run_concurrency_level(driver, person_ids, n_clients):
    stop_event = threading.Event()
    counters = {"ops": 0, "errors": 0}
    lock = threading.Lock()

    with ThreadPoolExecutor(max_workers=n_clients) as executor:
        futures = [
            executor.submit(worker, driver, person_ids, stop_event, counters, lock, i)
            for i in range(n_clients)
        ]

        time.sleep(DURATION_SECONDS)
        stop_event.set()

        for f in as_completed(futures):
            f.result()  # surface any unexpected exceptions

    throughput = counters["ops"] / DURATION_SECONDS
    return {
        "clients": n_clients,
        "total_ops": counters["ops"],
        "errors": counters["errors"],
        "duration_s": DURATION_SECONDS,
        "throughput_ops_per_sec": throughput,
    }


def cleanup_synthetic_writes(driver):
    """Remove benchmark-created nodes so repeated runs stay consistent."""
    with driver.session() as session:
        session.run(
            "MATCH (p:Person) WHERE p.personId STARTS WITH 'bench_' DETACH DELETE p"
        ).consume()


def main():
    if len(sys.argv) != 2:
        print("Usage: python workloads/mixed_concurrent.py <PLATFORM_PREFIX>")
        sys.exit(1)

    platform = sys.argv[1].upper()
    uri = os.getenv(f"{platform}_URI")
    user = os.getenv(f"{platform}_USER") or None
    password = os.getenv(f"{platform}_PASSWORD") or None

    if not uri:
        print(f"No {platform}_URI found in .env")
        sys.exit(1)

    print(f"=== Mixed concurrent workload: {platform} ===")
    auth = (user, password) if user else None
    driver = GraphDatabase.driver(
        uri, auth=auth, max_connection_pool_size=max(CONCURRENCY_LEVELS) + 5
    )
    driver.verify_connectivity()

    print("Fetching random person IDs for read pool...")
    person_ids = get_random_person_ids(driver, n=500)
    if not person_ids:
        print("No Person nodes found - did you run the loader for this platform?")
        sys.exit(1)
    print(f"  got {len(person_ids)} candidate IDs")

    os.makedirs("results", exist_ok=True)
    results = []

    for n_clients in CONCURRENCY_LEVELS:
        print(f"\nRunning {n_clients} concurrent clients for {DURATION_SECONDS}s "
              f"({int(READ_WRITE_RATIO*100)}% read / {int((1-READ_WRITE_RATIO)*100)}% write)...")
        result = run_concurrency_level(driver, person_ids, n_clients)
        print(f"  throughput: {result['throughput_ops_per_sec']:.1f} ops/sec  "
              f"(total {result['total_ops']} ops, {result['errors']} errors)")
        results.append(result)

    print("\nCleaning up synthetic write nodes...")
    cleanup_synthetic_writes(driver)

    summary_path = f"results/mixed_concurrent_{platform.lower()}_summary.csv"
    with open(summary_path, "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["clients", "total_ops", "errors", "duration_s", "throughput_ops_per_sec"],
        )
        writer.writeheader()
        writer.writerows(results)

    print(f"\nSaved summary to {summary_path}")
    driver.close()


if __name__ == "__main__":
    main()
