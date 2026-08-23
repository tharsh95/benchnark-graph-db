.PHONY: help setup teardown dataset dedupe load \
        load-selfhosted load-aura load-cognodb load-memgraph load-arango \
        check check-selfhosted check-aura check-cognodb check-memgraph check-arango \
        reset-local reset-cloud clean-data \
        traversal aggregation lookup mixed \
        traversal-selfhosted traversal-aura traversal-cognodb traversal-memgraph traversal-arango \
        aggregation-selfhosted aggregation-aura aggregation-cognodb aggregation-memgraph aggregation-arango \
        lookup-selfhosted lookup-aura lookup-cognodb lookup-memgraph lookup-arango \
        mixed-selfhosted mixed-aura mixed-cognodb mixed-memgraph mixed-arango \
        run run-bolt run-arango charts test all

PYTHON := $(shell [ -x venv/bin/python3 ] && echo venv/bin/python3 || echo python3)

help:
	@echo "CognoDB Benchmark — available commands:"
	@echo ""
	@echo "SETUP / DATA"
	@echo "  make setup             Start Memgraph/ArangoDB/Neo4j Docker containers"
	@echo "  make teardown          Stop and remove Docker containers"
	@echo "  make dataset           Download IMDb data + generate CSV files"
	@echo "  make dedupe            Remove duplicate ACTED_IN edges"
	@echo "  make clean-data        Delete generated dataset files"
	@echo ""
	@echo "LOADING"
	@echo "  make load              Load dataset into all 5 platforms"
	@echo "  make load-selfhosted   Load into self-hosted Neo4j"
	@echo "  make load-aura         Load into Neo4j Aura"
	@echo "  make load-cognodb      Load into CognoDB"
	@echo "  make load-memgraph     Load into Memgraph"
	@echo "  make load-arango       Load into ArangoDB"
	@echo ""
	@echo "VERIFICATION"
	@echo "  make check             Check all 5 platforms"
	@echo "  make check-selfhosted Check self-hosted Neo4j"
	@echo "  make check-aura        Check Neo4j Aura"
	@echo "  make check-cognodb     Check CognoDB"
	@echo "  make check-memgraph    Check Memgraph"
	@echo "  make check-arango      Check ArangoDB"
	@echo ""
	@echo "BENCHMARKS"
	@echo "  make run               Run all available workloads"
	@echo "  make run-bolt          Run traversal/aggregation/lookup/mixed on Bolt platforms"
	@echo "  make run-arango        Run all ArangoDB workloads"
	@echo ""
	@echo "  make traversal         Run traversal on all platforms"
	@echo "  make aggregation       Run aggregation on all platforms"
	@echo "  make lookup            Run lookup on all platforms"
	@echo "  make mixed             Run concurrent workload on all platforms"
	@echo ""
	@echo "PLATFORM-SPECIFIC BENCHMARKS"
	@echo "  make traversal-selfhosted"
	@echo "  make traversal-aura"
	@echo "  make traversal-cognodb"
	@echo "  make traversal-memgraph"
	@echo "  make traversal-arango"
	@echo ""
	@echo "  make aggregation-selfhosted"
	@echo "  make aggregation-aura"
	@echo "  make aggregation-cognodb"
	@echo "  make aggregation-memgraph"
	@echo "  make aggregation-arango"
	@echo ""
	@echo "  make lookup-selfhosted"
	@echo "  make lookup-aura"
	@echo "  make lookup-cognodb"
	@echo "  make lookup-memgraph"
	@echo "  make lookup-arango"
	@echo ""
	@echo "  make mixed-selfhosted"
	@echo "  make mixed-aura"
	@echo "  make mixed-cognodb"
	@echo "  make mixed-memgraph"
	@echo "  make mixed-arango"
	@echo ""
	@echo "OTHER"
	@echo "  make reset-local      Wipe + restart Docker platforms"
	@echo "  make reset-cloud      Wipe CognoDB + Aura"
	@echo "  make charts            Generate charts from results"
	@echo "  make test              Test platform connectivity"
	@echo "  make all               Full local pipeline"
	@echo ""


# ============================================================
# SETUP / DATA
# ============================================================

setup:
	chmod +x setup_docker.sh
	./setup_docker.sh

teardown:
	docker rm -f memgraph arangodb neo4j-selfhosted 2>/dev/null || true
	@echo "Docker containers removed."

dataset:
	$(PYTHON) prepare_dataset.py

dedupe:
	$(PYTHON) dedupe_edges.py

clean-data:
	rm -rf data/raw data/*.csv
	@echo "Removed data/raw/ and data/*.csv."


# ============================================================
# LOADERS
# ============================================================

load:
	chmod +x load_all.sh
	./load_all.sh

load-selfhosted:
	$(PYTHON) loaders/neo4j_selfhosted_loader.py

load-aura:
	$(PYTHON) loaders/neo4j_aura_loader.py

load-cognodb:
	$(PYTHON) loaders/cognodb_loader.py

load-memgraph:
	$(PYTHON) loaders/memgraph_loader.py

load-arango:
	$(PYTHON) loaders/arango_loader.py


# ============================================================
# VERIFICATION
# ============================================================

check:
	@echo "=== Neo4j Self-hosted ==="
	-$(PYTHON) check_loaded.py NEO4J_SELFHOSTED
	@echo ""
	@echo "=== Neo4j Aura ==="
	-$(PYTHON) check_loaded.py AURA
	@echo ""
	@echo "=== Memgraph ==="
	-$(PYTHON) check_loaded.py MEMGRAPH
	@echo ""
	@echo "=== CognoDB ==="
	-$(PYTHON) check_loaded.py COGNODB
	@echo ""
	@echo "=== ArangoDB ==="
	-$(PYTHON) check_loaded_arango.py

check-selfhosted:
	$(PYTHON) check_loaded.py NEO4J_SELFHOSTED

check-aura:
	$(PYTHON) check_loaded.py AURA

check-cognodb:
	$(PYTHON) check_loaded.py COGNODB

check-memgraph:
	$(PYTHON) check_loaded.py MEMGRAPH

check-arango:
	$(PYTHON) check_loaded_arango.py


# ============================================================
# RESET
# ============================================================

reset-local: teardown setup
	@echo "Local Docker platforms reset."

reset-cloud:
	$(PYTHON) clear_platform.py COGNODB
	$(PYTHON) clear_platform.py AURA
	@echo "CognoDB and Aura wiped."


# ============================================================
# TRAVERSAL
# ============================================================

traversal-selfhosted:
	$(PYTHON) workloads/traversal.py NEO4J_SELFHOSTED

traversal-aura:
	$(PYTHON) workloads/traversal.py AURA

traversal-cognodb:
	$(PYTHON) workloads/traversal.py COGNODB

traversal-memgraph:
	$(PYTHON) workloads/traversal.py MEMGRAPH

traversal-arango:
	$(PYTHON) workloads/traversal_arango.py

traversal:
	$(MAKE) traversal-selfhosted
	$(MAKE) traversal-aura
	$(MAKE) traversal-cognodb
	$(MAKE) traversal-memgraph
	$(MAKE) traversal-arango


# ============================================================
# AGGREGATION
# ============================================================

aggregation-selfhosted:
	$(PYTHON) workloads/aggregation.py NEO4J_SELFHOSTED

aggregation-aura:
	$(PYTHON) workloads/aggregation.py AURA

aggregation-cognodb:
	$(PYTHON) workloads/aggregation.py COGNODB

aggregation-memgraph:
	$(PYTHON) workloads/aggregation.py MEMGRAPH

aggregation-arango:
	$(PYTHON) workloads/aggregation_arango.py

aggregation:
	$(MAKE) aggregation-selfhosted
	$(MAKE) aggregation-aura
	$(MAKE) aggregation-cognodb
	$(MAKE) aggregation-memgraph
	$(MAKE) aggregation-arango


# ============================================================
# LOOKUP
# ============================================================

lookup-selfhosted:
	$(PYTHON) workloads/lookup.py NEO4J_SELFHOSTED

lookup-aura:
	$(PYTHON) workloads/lookup.py AURA

lookup-cognodb:
	$(PYTHON) workloads/lookup.py COGNODB

lookup-memgraph:
	$(PYTHON) workloads/lookup.py MEMGRAPH

lookup-arango:
	$(PYTHON) workloads/lookup_arango.py

lookup:
	$(MAKE) lookup-selfhosted
	$(MAKE) lookup-aura
	$(MAKE) lookup-cognodb
	$(MAKE) lookup-memgraph
	$(MAKE) lookup-arango


# ============================================================
# MIXED CONCURRENT
# ============================================================

mixed-selfhosted:
	$(PYTHON) workloads/mixed_concurrent.py NEO4J_SELFHOSTED

mixed-aura:
	$(PYTHON) workloads/mixed_concurrent.py AURA

mixed-cognodb:
	$(PYTHON) workloads/mixed_concurrent.py COGNODB

mixed-memgraph:
	$(PYTHON) workloads/mixed_concurrent.py MEMGRAPH

mixed-arango:
	$(PYTHON) workloads/mixed_concurrent_arango.py

mixed:
	$(MAKE) mixed-selfhosted
	$(MAKE) mixed-aura
	$(MAKE) mixed-cognodb
	$(MAKE) mixed-memgraph
	$(MAKE) mixed-arango


# ============================================================
# RUN ALL
# ============================================================

run-bolt:
	$(MAKE) traversal-selfhosted
	$(MAKE) aggregation-selfhosted
	$(MAKE) lookup-selfhosted
	$(MAKE) mixed-selfhosted
	$(MAKE) traversal-aura
	$(MAKE) aggregation-aura
	$(MAKE) lookup-aura
	$(MAKE) mixed-aura
	$(MAKE) traversal-cognodb
	$(MAKE) aggregation-cognodb
	$(MAKE) lookup-cognodb
	$(MAKE) mixed-cognodb
	$(MAKE) traversal-memgraph
	$(MAKE) aggregation-memgraph
	$(MAKE) lookup-memgraph
	$(MAKE) mixed-memgraph

run-arango:
	$(MAKE) traversal-arango
	$(MAKE) aggregation-arango
	$(MAKE) lookup-arango
	$(MAKE) mixed-arango

run:
	chmod +x run_all.sh
	./run_all.sh


# ============================================================
# TESTS / CHARTS
# ============================================================

test:
	$(PYTHON) test_connections.py

charts:
	$(PYTHON) generate_charts.py


# ============================================================
# FULL PIPELINE
# ============================================================

all: setup dataset dedupe load test run
	@echo "Full pipeline complete."
	@echo "See results/ for benchmark CSVs."