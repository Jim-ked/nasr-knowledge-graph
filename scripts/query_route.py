import argparse
import os

from neo4j import GraphDatabase


def route_query(max_depth):
    if not 1 <= max_depth <= 80:
        raise ValueError("max_depth 必须在 1 到 80 之间")
    return f"""
        MATCH p =
        (start:Airport {{ARPT_ID: $origin}})
        -[:ROUTE_EDGE*1..{max_depth}]->
        (end:Airport {{ARPT_ID: $dest}})
        WITH p, nodes(p) AS ns
        WHERE all(n IN ns WHERE single(m IN ns WHERE m = n))
          AND none(n IN ns[1..size(ns)-1] WHERE n:Airport)
        RETURN p
        LIMIT $limit
    """


def find_paths(driver, origin, dest, max_depth=40, limit=10):
    if not 1 <= limit <= 100:
        raise ValueError("limit 必须在 1 到 100 之间")
    query = route_query(max_depth)
    with driver.session() as session:
        return [
            record["p"]
            for record in session.run(
                query,
                origin=origin.strip().upper(),
                dest=dest.strip().upper(),
                limit=limit,
            )
        ]


def node_text(node):
    labels = set(node.labels)
    if "Airport" in labels:
        return f"{node.get('ARPT_ID', '?')} {node.get('ARPT_NAME', '')}".strip()
    if "Fix" in labels:
        return f"{node.get('FIX_ID', '?')} [FIX]"
    return (
        f"{node.get('NAV_ID', '?')} "
        f"[NAVAID: {node.get('NAV_TYPE', '?')}] "
        f"{node.get('NAME', '')}"
    ).strip()


def print_paths(paths):
    if not paths:
        print("未找到路径")
        return

    for number, path in enumerate(paths, start=1):
        print(f"\nPath {number} | hops={len(path.relationships)}")
        print(node_text(path.nodes[0]))
        for relationship, node in zip(path.relationships, path.nodes[1:]):
            route_keys = relationship.get("sourceRouteKeys", "")
            keys = [key for key in route_keys.split("|") if key]
            shown = "|".join(keys[:3])
            if len(keys) > 3:
                shown += f" ... ({len(keys)} total)"
            print(
                f" -> {node_text(node)}\n"
                f"    directionType={relationship.get('directionType')} "
                f"sourceRouteCount={relationship.get('sourceRouteCount')} "
                f"sourceRouteKeys={shown}"
            )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--origin", required=True)
    parser.add_argument("--dest", required=True)
    parser.add_argument("--max-depth", type=int, default=40)
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    if not 1 <= args.max_depth <= 80:
        parser.error("--max-depth 必须在 1 到 80 之间")
    if not 1 <= args.limit <= 100:
        parser.error("--limit 必须在 1 到 100 之间")

    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "password")
    with GraphDatabase.driver(uri, auth=(user, password)) as driver:
        driver.verify_connectivity()
        paths = find_paths(
            driver,
            args.origin,
            args.dest,
            max_depth=args.max_depth,
            limit=args.limit,
        )
    print_paths(paths)


if __name__ == "__main__":
    main()
