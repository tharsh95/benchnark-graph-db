#!/usr/bin/env bash
#
# Starts the 3 self-hosted platforms (Memgraph, ArangoDB, Neo4j) as Docker
# containers, each capped to 0.5 vCPU / 512MB RAM to match CognoDB's free
# tier specs (see README.md section 1 for the fairness rationale).
#
# Requires Docker to be installed and running. CognoDB and Neo4j AuraDB are
# managed cloud services and are NOT started by this script - you must
# create free-tier accounts for those separately (see README.md section 8)
# and fill in their credentials in .env.
#
# Usage: ./setup_docker.sh
#
set -e

ARANGO_PASSWORD="${ARANGO_PASSWORD:-benchmarkpass123}"
NEO4J_PASSWORD="${NEO4J_SELFHOSTED_PASSWORD:-benchmarkpass123}"

echo "=========================================="
echo " Starting self-hosted platforms via Docker"
echo " (each capped to 0.5 vCPU / 512MB RAM)"
echo "=========================================="

if ! docker info > /dev/null 2>&1; then
    echo "ERROR: Docker is not running. Start Docker Desktop (or the Docker daemon) and retry."
    exit 1
fi

echo ""
echo "-- Memgraph --"
if docker ps -a --format '{{.Names}}' | grep -q '^memgraph$'; then
    echo "  container 'memgraph' already exists, skipping (run 'docker rm -f memgraph' to reset)"
else
    docker run -d --name memgraph \
        --cpus="0.5" --memory="512m" \
        -p 7687:7687 \
        memgraph/memgraph
    echo "  started on bolt://localhost:7687"
fi

echo ""
echo "-- ArangoDB --"
if docker ps -a --format '{{.Names}}' | grep -q '^arangodb$'; then
    echo "  container 'arangodb' already exists, skipping (run 'docker rm -f arangodb' to reset)"
else
    docker run -d --name arangodb \
        --cpus="0.5" --memory="512m" \
        -p 8529:8529 \
        -e ARANGO_ROOT_PASSWORD="$ARANGO_PASSWORD" \
        arangodb/arangodb
    echo "  started on http://localhost:8529 (user: root, password: $ARANGO_PASSWORD)"
fi

echo ""
echo "-- Neo4j (self-hosted) --"
if docker ps -a --format '{{.Names}}' | grep -q '^neo4j-selfhosted$'; then
    echo "  container 'neo4j-selfhosted' already exists, skipping (run 'docker rm -f neo4j-selfhosted' to reset)"
else
    docker run -d --name neo4j-selfhosted \
        --cpus="0.5" --memory="512m" \
        -p 7688:7687 -p 7475:7474 \
        -e NEO4J_AUTH="neo4j/$NEO4J_PASSWORD" \
        -e NEO4J_server_memory_heap_initial__size=256m \
        -e NEO4J_server_memory_heap_max__size=256m \
        -e NEO4J_server_memory_pagecache_size=64m \
        neo4j:5
    echo "  started on bolt://localhost:7688 (user: neo4j, password: $NEO4J_PASSWORD)"
fi

echo ""
echo "Waiting 20s for containers to finish booting..."
sleep 20

echo ""
echo "=========================================="
echo " Done. Next steps:"
echo "  1. Copy .env.example to .env and fill in credentials"
echo "     (use the passwords printed above for Memgraph/ArangoDB/Neo4j,"
echo "      plus your own CognoDB + Aura URIs/passwords)"
echo "  2. Run: python test_connections.py"
echo "  3. Run: ./load_all.sh"
echo "=========================================="
