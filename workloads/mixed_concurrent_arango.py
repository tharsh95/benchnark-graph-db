"""
Mixed concurrent workload for ArangoDB: sustained queries/second under
concurrent load. Mirrors workloads/mixed_concurrent.py so results are
directly comparable.

Usage: python workloads/mixed_concurrent_arango.py
"""
import csv
import os
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from arango import ArangoClient
from dotenv import load_dotenv

load_dotenv()

CONCURRENCY_LEVELS = [10, 40]
DURATION_SECONDS = 15
READ_WRITE_RATIO = 0.8

READ_QUERY = """
    FOR p IN Person
        FILTER p.personId == @personId
        RETURN p.name
"""


def get_random_person_ids(db, n=500):
    cursor = db.aql.execute(f"FOR p IN Person LIMIT {n} RETURN p.personId")
    return list(cursor)


def worker(uri, db_name, user, password, person_ids, stop_event, counters, lock, worker_id):
    # Each thread gets its own client/db handle - python-arango's http session
    # isn't guaranteed thread-safe when shared across threads.
    local_client = ArangoClient(hosts=uri)
    db = local_client.db(db_name, username=user, password=password)

    local_ops = 0
    local_errors = 0
    write_counter = 0

    while not stop_event.is_set():
        try:
            is_write = random.random() > READ_WRITE_RATIO
            if is_write:
                write_counter += 1
                synthetic_id = f"bench_{worker_id}_{write_counter}"
                db.collection("Person").insert(
                    {"_key": synthetic_id, "personId": synthetic_id, "name": "Benchmark Synthetic"}
                )
            else:
                pid = random.choice(person_ids)
                cursor = db.aql.execute(READ_QUERY, bind_vars={"personId": pid})
                list(cursor)
            local_ops += 1
        except Exception:
            local_errors += 1

    with lock:
        counters["ops"] += local_ops
        counters["errors"] += local_errors


def run_concurrency_level(uri, db_name, user, password, person_ids, n_clients):
    stop_event = threading.Event()
    counters = {"ops": 0, "errors": 0}
    lock = threading.Lock()

    with ThreadPoolExecutor(max_workers=n_clients) as executor:
        futures = [
            executor.submit(
                worker, uri, db_name, user, password, person_ids, stop_event, counters, lock, i
            )
            for i in range(n_clients)
        ]

        time.sleep(DURATION_SECONDS)
        stop_event.set()

        for f in as_completed(futures):
            f.result()

    throughput = counters["ops"] / DURATION_SECONDS
    return {
        "clients": n_clients,
        "total_ops": counters["ops"],
        "errors": counters["errors"],
        "duration_s": DURATION_SECONDS,
        "throughput_ops_per_sec": throughput,
    }


def cleanup_synthetic_writes(db):
    db.aql.execute(
        "FOR p IN Person FILTER STARTS_WITH(p.personId, 'bench_') REMOVE p IN Person"
    )


def main():
    uri = os.getenv("ARANGO_URI")
    user = os.getenv("ARANGO_USER")
    password = os.getenv("ARANGO_PASSWORD")
    db_name = os.getenv("ARANGO_DB", "benchmark")

    print("=== Mixed concurrent workload: ARANGO ===")
    client = ArangoClient(hosts=uri)
    db = client.db(db_name, username=user, password=password)

    print("Fetching random person IDs for read pool...")
    person_ids = get_random_person_ids(db, n=500)
    if not person_ids:
        print("No people found - did you run the ArangoDB loader?")
        return
    print(f"  got {len(person_ids)} candidate IDs")

    os.makedirs("results", exist_ok=True)
    results = []

    for n_clients in CONCURRENCY_LEVELS:
        print(f"\nRunning {n_clients} concurrent clients for {DURATION_SECONDS}s "
              f"({int(READ_WRITE_RATIO*100)}% read / {int((1-READ_WRITE_RATIO)*100)}% write)...")
        result = run_concurrency_level(uri, db_name, user, password, person_ids, n_clients)
        print(f"  throughput: {result['throughput_ops_per_sec']:.1f} ops/sec  "
              f"(total {result['total_ops']} ops, {result['errors']} errors)")
        results.append(result)

    print("\nCleaning up synthetic write nodes...")
    cleanup_synthetic_writes(db)

    summary_path = "results/mixed_concurrent_arango_summary.csv"
    with open(summary_path, "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["clients", "total_ops", "errors", "duration_s", "throughput_ops_per_sec"],
        )
        writer.writeheader()
        writer.writerows(results)

    print(f"\nSaved summary to {summary_path}")


if __name__ == "__main__":
    main()
