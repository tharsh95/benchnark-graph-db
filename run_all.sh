#!/usr/bin/env bash
#
# Runs every workload (traversal, lookup, aggregation, mixed_concurrent)
# against every platform (CognoDB, Aura, Memgraph, self-hosted Neo4j,
# ArangoDB). Assumes .env is filled in, all 5 databases are already loaded
# (see loaders/), and dependencies are installed (pip install -r requirements.txt).
#
# Usage: ./run_all.sh
#   or:  bash run_all.sh
#
if [ -x "venv/bin/python3" ]; then
    PYTHON="venv/bin/python3"
else
    PYTHON="python3"
fi
set -e  # stop on first failure so a broken platform doesn't silently skip

echo "=========================================="
echo " Pre-flight: checking all 5 platforms are reachable"
echo "=========================================="
if ! python3 test_connections.py; then
    echo ""
    echo "ERROR: not all platforms are reachable. Before running this script:"
    echo "  1. Run ./setup_docker.sh to start Memgraph/ArangoDB/Neo4j containers"
    echo "  2. Fill in .env with your CognoDB + Neo4j Aura credentials"
    echo "     (copy .env.example to .env first if you haven't)"
    echo "  3. Run ./load_all.sh to load the dataset into all 5 platforms"
    echo "  4. Re-run this script"
    exit 1
fi

BOLT_PLATFORMS=("COGNODB" "AURA" "MEMGRAPH" "NEO4J_SELFHOSTED")

echo "=========================================="
echo " Step 1/2: bolt-protocol platforms"
echo " (CognoDB, Aura, Memgraph, self-hosted Neo4j)"
echo "=========================================="

for platform in "${BOLT_PLATFORMS[@]}"; do
    echo ""
    echo "------ $platform ------"
    python3 workloads/traversal.py "$platform"
    python3 workloads/lookup.py "$platform"
    python3 workloads/aggregation.py "$platform"
    python3 workloads/mixed_concurrent.py "$platform"
done

echo ""
echo "=========================================="
echo " Step 2/2: ArangoDB (AQL, separate scripts)"
echo "=========================================="
python3 workloads/traversal_arango.py
python3 workloads/lookup_arango.py
python3 workloads/aggregation_arango.py
python3 workloads/mixed_concurrent_arango.py

echo ""
echo "=========================================="
echo " Generating charts"
echo "=========================================="
python3 generate_charts.py

echo ""
echo "=========================================="
echo " All workloads complete."
echo " Results saved to results/*.csv"
echo " Charts saved to results/charts/*.png"
echo "=========================================="
