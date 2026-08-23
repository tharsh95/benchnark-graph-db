"""
Generates comparison charts from results/*.csv for the README.

Reads the summary CSVs produced by each workload script and saves PNG
charts to results/charts/. Run this after all workloads have completed
for all 5 platforms.

Usage: python generate_charts.py
"""
import csv
import os

import matplotlib.pyplot as plt
import numpy as np

RESULTS_DIR = "results"
CHARTS_DIR = os.path.join(RESULTS_DIR, "charts")

PLATFORMS = ["cognodb", "aura", "memgraph", "neo4j_selfhosted", "arango"]
PLATFORM_LABELS = {
    "cognodb": "CognoDB",
    "aura": "Neo4j Aura",
    "memgraph": "Memgraph",
    "neo4j_selfhosted": "Neo4j (self-hosted)",
    "arango": "ArangoDB",
}
COLORS = {
    "cognodb": "#e63946",
    "aura": "#457b9d",
    "memgraph": "#2a9d8f",
    "neo4j_selfhosted": "#e9c46a",
    "arango": "#8338ec",
}


def read_summary(path):
    if not os.path.exists(path):
        return None
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def chart_traversal():
    hops = [1, 2, 3]
    fig, ax = plt.subplots(figsize=(10, 6))
    width = 0.15
    x = np.arange(len(hops))

    for i, platform in enumerate(PLATFORMS):
        rows = read_summary(f"{RESULTS_DIR}/traversal_{platform}_summary.csv")
        if not rows:
            continue
        p50_by_hop = {int(r["hop"]): float(r["p50_ms"]) for r in rows}
        values = [p50_by_hop.get(h, 0) for h in hops]
        ax.bar(x + i * width, values, width, label=PLATFORM_LABELS[platform], color=COLORS[platform])

    ax.set_xlabel("Hop depth")
    ax.set_ylabel("p50 latency (ms, log scale)")
    ax.set_yscale("log")
    ax.set_title("Traversal latency by hop depth (p50)")
    ax.set_xticks(x + width * 2)
    ax.set_xticklabels([f"{h}-hop" for h in hops])
    ax.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(CHARTS_DIR, "traversal_latency.png"), dpi=150)
    plt.close(fig)
    print("  saved traversal_latency.png")


def chart_lookup():
    queries = ["point_lookup", "filtered_lookup"]
    query_labels = ["Point lookup\n(indexed)", "Filtered lookup\n(unindexed)"]
    fig, ax = plt.subplots(figsize=(10, 6))
    width = 0.15
    x = np.arange(len(queries))

    for i, platform in enumerate(PLATFORMS):
        rows = read_summary(f"{RESULTS_DIR}/lookup_{platform}_summary.csv")
        if not rows:
            continue
        p50_by_query = {r["query"]: float(r["p50_ms"]) for r in rows}
        values = [p50_by_query.get(q, 0) for q in queries]
        ax.bar(x + i * width, values, width, label=PLATFORM_LABELS[platform], color=COLORS[platform])

    ax.set_ylabel("p50 latency (ms, log scale)")
    ax.set_yscale("log")
    ax.set_title("Lookup latency: indexed vs unindexed (p50)")
    ax.set_xticks(x + width * 2)
    ax.set_xticklabels(query_labels)
    ax.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(CHARTS_DIR, "lookup_latency.png"), dpi=150)
    plt.close(fig)
    print("  saved lookup_latency.png")


def chart_aggregation():
    fig, ax = plt.subplots(figsize=(10, 6))
    labels, values, colors = [], [], []

    for platform in PLATFORMS:
        rows = read_summary(f"{RESULTS_DIR}/aggregation_{platform}_summary.csv")
        if not rows:
            continue
        labels.append(PLATFORM_LABELS[platform])
        values.append(float(rows[0]["p50_ms"]))
        colors.append(COLORS[platform])

    # sort fastest to slowest
    order = np.argsort(values)
    labels = [labels[i] for i in order]
    values = [values[i] for i in order]
    colors = [colors[i] for i in order]

    ax.barh(labels, values, color=colors)
    ax.set_xlabel("p50 latency (ms, log scale)")
    ax.set_xscale("log")
    ax.set_title("Aggregation latency: count/group-by ACTED_IN by startYear (p50)")
    fig.tight_layout()
    fig.savefig(os.path.join(CHARTS_DIR, "aggregation_latency.png"), dpi=150)
    plt.close(fig)
    print("  saved aggregation_latency.png")


def chart_mixed_concurrent():
    fig, ax = plt.subplots(figsize=(10, 6))
    width = 0.35
    x = np.arange(len(PLATFORMS))

    throughput_10, throughput_40 = [], []
    labels = []

    for platform in PLATFORMS:
        rows = read_summary(f"{RESULTS_DIR}/mixed_concurrent_{platform}_summary.csv")
        if not rows:
            continue
        by_clients = {int(r["clients"]): float(r["throughput_ops_per_sec"]) for r in rows}
        throughput_10.append(by_clients.get(10, 0))
        throughput_40.append(by_clients.get(40, 0))
        labels.append(PLATFORM_LABELS[platform])

    x = np.arange(len(labels))
    ax.bar(x - width / 2, throughput_10, width, label="10 clients", color="#a8dadc")
    ax.bar(x + width / 2, throughput_40, width, label="40 clients", color="#1d3557")

    ax.set_ylabel("Throughput (ops/sec)")
    ax.set_title("Mixed concurrent workload throughput (80% read / 20% write)")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=20, ha="right")
    ax.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(CHARTS_DIR, "mixed_concurrent_throughput.png"), dpi=150)
    plt.close(fig)
    print("  saved mixed_concurrent_throughput.png")


def chart_load_time():
    fig, ax = plt.subplots(figsize=(10, 6))
    # Hardcoded from the actual benchmark run - update if you rerun loaders
    load_times = {
        "cognodb": 227.0,
        "aura": 46.3,
        "memgraph": 7.5,
        "neo4j_selfhosted": 16.9,
        "arango": 9.8,
    }
    labels = [PLATFORM_LABELS[p] for p in PLATFORMS]
    values = [load_times[p] for p in PLATFORMS]
    colors = [COLORS[p] for p in PLATFORMS]

    order = np.argsort(values)
    labels = [labels[i] for i in order]
    values = [values[i] for i in order]
    colors = [colors[i] for i in order]

    ax.barh(labels, values, color=colors)
    ax.set_xlabel("Load time (seconds, log scale)")
    ax.set_xscale("log")
    ax.set_title("Data ingest time: 158,882 nodes + 175,889 relationships")
    fig.tight_layout()
    fig.savefig(os.path.join(CHARTS_DIR, "load_time.png"), dpi=150)
    plt.close(fig)
    print("  saved load_time.png")


def main():
    os.makedirs(CHARTS_DIR, exist_ok=True)
    print("Generating charts...")
    chart_load_time()
    chart_traversal()
    chart_lookup()
    chart_aggregation()
    chart_mixed_concurrent()
    print(f"\nAll charts saved to {CHARTS_DIR}/")


if __name__ == "__main__":
    main()
