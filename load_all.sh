#!/usr/bin/env bash

#
# Loads the prepared dataset into all 5 platforms.
# Skips a platform if it already has the expected counts.
# If one platform fails, the script continues with the others.
#
# Usage:
#   ./load_all.sh
#

PYTHON="${PYTHON:-python}"

if [ ! -f "data/nodes_people.csv" ]; then
    echo "ERROR: data/nodes_people.csv not found."
    echo "Run 'python prepare_dataset.py' first."
    exit 1
fi

echo "=========================================="
echo " Loading dataset into all 5 platforms"
echo "=========================================="

FAILED_PLATFORMS=""

echo ""
echo "-- CognoDB --"
if $PYTHON check_loaded.py COGNODB; then
    echo "  already loaded, skipping"
else
    echo "  loading CognoDB..."
    if $PYTHON loaders/cognodb_loader.py; then
        echo "  CognoDB loaded successfully"
    else
        echo "  ERROR: CognoDB loading failed"
        FAILED_PLATFORMS="$FAILED_PLATFORMS COGNODB"
    fi
fi


echo ""
echo "-- Neo4j AuraDB --"
if $PYTHON check_loaded.py AURA; then
    echo "  already loaded, skipping"
else
    echo "  loading Neo4j AuraDB..."
    if $PYTHON loaders/neo4j_aura_loader.py; then
        echo "  Neo4j AuraDB loaded successfully"
    else
        echo "  ERROR: Neo4j AuraDB loading failed"
        FAILED_PLATFORMS="$FAILED_PLATFORMS AURA"
    fi
fi


echo ""
echo "-- Neo4j self-hosted --"
if $PYTHON check_loaded.py NEO4J_SELFHOSTED; then
    echo "  already loaded, skipping"
else
    echo "  loading Neo4j self-hosted..."
    if $PYTHON loaders/neo4j_selfhosted_loader.py; then
        echo "  Neo4j self-hosted loaded successfully"
    else
        echo "  ERROR: Neo4j self-hosted loading failed"
        FAILED_PLATFORMS="$FAILED_PLATFORMS NEO4J_SELFHOSTED"
    fi
fi


echo ""
echo "-- Memgraph --"
if $PYTHON check_loaded.py MEMGRAPH; then
    echo "  already loaded, skipping"
else
    echo "  loading Memgraph..."
    if $PYTHON loaders/memgraph_loader.py; then
        echo "  Memgraph loaded successfully"
    else
        echo "  ERROR: Memgraph loading failed"
        FAILED_PLATFORMS="$FAILED_PLATFORMS MEMGRAPH"
    fi
fi


echo ""
echo "-- ArangoDB --"
if $PYTHON check_loaded_arango.py; then
    echo "  already loaded, skipping"
else
    echo "  loading ArangoDB..."
    if $PYTHON loaders/arangodb_loader.py; then
        echo "  ArangoDB loaded successfully"
    else
        echo "  ERROR: ArangoDB loading failed"
        FAILED_PLATFORMS="$FAILED_PLATFORMS ARANGO"
    fi
fi


echo ""
echo "=========================================="

if [ -n "$FAILED_PLATFORMS" ]; then
    echo " Loading completed with failures."
    echo ""
    echo " Failed platforms:$FAILED_PLATFORMS"
    echo ""
    echo " Fix the failed platforms before running benchmarks."
    exit 1
else
    echo " All platforms checked/loaded successfully."
    echo ""
    echo " Next:"
    echo "   ./run_all.sh"
fi

echo "=========================================="