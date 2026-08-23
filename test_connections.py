"""
Quick sanity check: verifies we can connect to every platform before
building loaders/workloads on top of them.

Run: python test_connections.py
"""
import os
import sys
from dotenv import load_dotenv

load_dotenv()


def test_bolt(name, uri, user, password):
    """Test a bolt-protocol database (CognoDB, Aura, Memgraph)."""
    from neo4j import GraphDatabase

    try:
        auth = (user, password) if user else None
        driver = GraphDatabase.driver(uri, auth=auth)
        driver.verify_connectivity()
        with driver.session() as session:
            result = session.run("RETURN 1 AS ok")
            record = result.single()
            assert record["ok"] == 1
        driver.close()
        print(f"  [OK] {name}: connected ({uri})")
        return True
    except Exception as e:
        print(f"  [FAIL] {name}: {e}")
        return False


def test_arango(name, uri, user, password, db_name):
    """Test ArangoDB (HTTP + AQL)."""
    from arango import ArangoClient

    try:
        client = ArangoClient(hosts=uri)
        sys_db = client.db("_system", username=user, password=password)

        if not sys_db.has_database(db_name):
            sys_db.create_database(db_name)
            print(f"  (created database '{db_name}')")

        db = client.db(db_name, username=user, password=password)
        cursor = db.aql.execute("RETURN 1")
        result = list(cursor)
        assert result == [1]
        print(f"  [OK] {name}: connected ({uri})")
        return True
    except Exception as e:
        print(f"  [FAIL] {name}: {e}")
        return False


def main():
    print("Testing connections to all platforms...\n")

    results = {}

    print("CognoDB:")
    results["CognoDB"] = test_bolt(
        "CognoDB",
        os.getenv("COGNODB_URI"),
        os.getenv("COGNODB_USER"),
        os.getenv("COGNODB_PASSWORD"),
    )

    print("\nNeo4j Aura:")
    results["Aura"] = test_bolt(
        "Aura",
        os.getenv("AURA_URI"),
        os.getenv("AURA_USER"),
        os.getenv("AURA_PASSWORD"),
    )

    print("\nMemgraph:")
    results["Memgraph"] = test_bolt(
        "Memgraph",
        os.getenv("MEMGRAPH_URI"),
        os.getenv("MEMGRAPH_USER") or None,
        os.getenv("MEMGRAPH_PASSWORD") or None,
    )
    
    print("\nNeo4j (self-hosted):")
    results["Neo4j-SelfHosted"] = test_bolt(
        "Neo4j-SelfHosted",
        os.getenv("NEO4J_SELFHOSTED_URI"),
        os.getenv("NEO4J_SELFHOSTED_USER"),
        os.getenv("NEO4J_SELFHOSTED_PASSWORD"),
    )

    print("\nArangoDB:")
    results["ArangoDB"] = test_arango(
        "ArangoDB",
        os.getenv("ARANGO_URI"),
        os.getenv("ARANGO_USER"),
        os.getenv("ARANGO_PASSWORD"),
        os.getenv("ARANGO_DB", "benchmark"),
    )

    print("\n" + "=" * 40)
    passed = sum(results.values())
    total = len(results)
    print(f"Result: {passed}/{total} platforms connected")

    if passed < total:
        sys.exit(1)


if __name__ == "__main__":
    main()
