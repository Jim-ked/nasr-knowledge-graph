import os
from pathlib import Path

from neo4j import GraphDatabase
from dotenv import load_dotenv

from query_route import find_paths


load_dotenv(Path(__file__).resolve().parents[1] / ".env")


COUNT_QUERIES = {
    "Airport": "MATCH (n:Airport) RETURN count(n) AS count",
    "Fix": "MATCH (n:Fix) RETURN count(n) AS count",
    "Navaid": "MATCH (n:Navaid) RETURN count(n) AS count",
    "ROUTE_EDGE": "MATCH ()-[r:ROUTE_EDGE]->() RETURN count(r) AS count",
}


def validate_graph(driver):
    results = {}
    with driver.session() as session:
        for name, query in COUNT_QUERIES.items():
            results[name] = session.run(query).single()["count"]
        results["empty_edge_keys"] = session.run(
            "MATCH ()-[r:ROUTE_EDGE]->() "
            "WHERE r.fromNodeKey IS NULL OR r.toNodeKey IS NULL "
            "RETURN count(r) AS count"
        ).single()["count"]
        results["self_loops"] = session.run(
            "MATCH (n)-[r:ROUTE_EDGE]->(n) RETURN count(r) AS count"
        ).single()["count"]

    for name, count in results.items():
        print(f"{name}: {count}")

    for origin, dest in (("ATL", "LAX"), ("ABE", "BDL"), ("ORD", "DFW")):
        paths, truncated = find_paths(
            driver, origin, dest, max_depth=40, limit=1
        )
        if paths:
            print(
                f"{origin} -> {dest}: "
                f"找到路径，hops={len(paths[0]['relationships'])}"
            )
        elif truncated:
            print(f"{origin} -> {dest}: 搜索队列超限")
        else:
            print(f"{origin} -> {dest}: 未找到路径")
    return results


def main():
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "password")
    with GraphDatabase.driver(uri, auth=(user, password)) as driver:
        driver.verify_connectivity()
        validate_graph(driver)


if __name__ == "__main__":
    main()
