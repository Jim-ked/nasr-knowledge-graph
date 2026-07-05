import argparse
import os
from collections import Counter, deque

from neo4j import GraphDatabase


AIRPORT_QUERY = """
    MATCH (a:Airport {ARPT_ID: $airport})
    RETURN a.nodeKey AS nodeKey,
           labels(a) AS labels,
           a.ARPT_ID AS arptId,
           a.ARPT_NAME AS arptName
"""

NEIGHBOR_RETURN = """
    MATCH (n {nodeKey: $nodeKey})-[r:ROUTE_EDGE]->(m)
    RETURN m.nodeKey AS nextNodeKey,
           labels(m) AS labels,
           m.ARPT_ID AS arptId,
           m.ARPT_NAME AS arptName,
           m.FIX_ID AS fixId,
           m.NAV_ID AS navId,
           m.NAV_TYPE AS navType,
           m.NAME AS navName,
           r.edgeKey AS edgeKey,
           r.directionType AS directionType,
           r.sourceRouteCount AS sourceRouteCount,
           r.sourceRouteKeys AS sourceRouteKeys
"""

NEIGHBOR_QUERY_ORIGINAL_FIRST = NEIGHBOR_RETURN + """
    ORDER BY CASE r.directionType WHEN 'original' THEN 0 ELSE 1 END,
             r.sourceRouteCount DESC,
             m.nodeKey
    LIMIT $neighborLimit
"""

NEIGHBOR_QUERY_ALL = NEIGHBOR_RETURN + """
    ORDER BY r.sourceRouteCount DESC, m.nodeKey
    LIMIT $neighborLimit
"""


def route_query(max_depth, limit):
    if not 1 <= max_depth <= 80:
        raise ValueError("max_depth 必须在 1 到 80 之间")
    if not 1 <= limit <= 100:
        raise ValueError("limit 必须在 1 到 100 之间")
    return f"""
        MATCH SHORTEST {limit}
        (p = (start:Airport {{ARPT_ID: $origin}})
             -[:ROUTE_EDGE*1..{max_depth}]->
             (end:Airport {{ARPT_ID: $dest}})
         WHERE all(n IN nodes(p)
                   WHERE single(m IN nodes(p) WHERE m = n))
           AND none(n IN nodes(p)[1..size(nodes(p))-1]
                    WHERE n:Airport))
        RETURN p
        LIMIT $limit
    """


def bfs_search(start_node, dest_key, get_neighbors,
               max_depth=40, limit=10, max_queue=50000):
    queue = deque([{"nodes": [start_node], "relationships": []}])
    queued_counts = Counter({start_node["nodeKey"]: 1})
    paths = []

    while queue and len(paths) < limit:
        path = queue.popleft()
        if len(path["relationships"]) >= max_depth:
            continue

        current_key = path["nodes"][-1]["nodeKey"]
        used_keys = {node["nodeKey"] for node in path["nodes"]}
        for next_node, relationship in get_neighbors(current_key):
            next_key = next_node["nodeKey"]
            if next_key in used_keys:
                continue

            next_path = {
                "nodes": [*path["nodes"], next_node],
                "relationships": [*path["relationships"], relationship],
            }
            if "Airport" in next_node["labels"]:
                if next_key == dest_key:
                    paths.append(next_path)
                    if len(paths) >= limit:
                        return paths, False
                continue

            if queued_counts[next_key] >= limit:
                continue
            if len(queue) >= max_queue:
                return paths, True
            queued_counts[next_key] += 1
            queue.append(next_path)

    return paths, False


def airport_node(session, airport_id):
    record = session.run(
        AIRPORT_QUERY, airport=airport_id.strip().upper()
    ).single()
    if record is None:
        return None
    return {
        "nodeKey": record["nodeKey"],
        "labels": record["labels"],
        "ARPT_ID": record["arptId"],
        "ARPT_NAME": record["arptName"],
    }


def neighbor_rows(session, node_key, neighbor_limit, prefer_original):
    query = (
        NEIGHBOR_QUERY_ORIGINAL_FIRST
        if prefer_original
        else NEIGHBOR_QUERY_ALL
    )
    rows = []
    for record in session.run(
        query, nodeKey=node_key, neighborLimit=neighbor_limit
    ):
        node = {
            "nodeKey": record["nextNodeKey"],
            "labels": record["labels"],
            "ARPT_ID": record["arptId"],
            "ARPT_NAME": record["arptName"],
            "FIX_ID": record["fixId"],
            "NAV_ID": record["navId"],
            "NAV_TYPE": record["navType"],
            "NAME": record["navName"],
        }
        relationship = {
            "edgeKey": record["edgeKey"],
            "directionType": record["directionType"],
            "sourceRouteCount": record["sourceRouteCount"],
            "sourceRouteKeys": record["sourceRouteKeys"],
        }
        rows.append((node, relationship))
    return rows


def find_paths_bfs(driver, origin, dest, max_depth=40, limit=10,
                   neighbor_limit=100, prefer_original=True,
                   max_queue=50000):
    with driver.session() as session:
        start = airport_node(session, origin)
        finish = airport_node(session, dest)
        if start is None or finish is None:
            return [], False

        neighbor_cache = {}

        def get_neighbors(node_key):
            if node_key not in neighbor_cache:
                neighbor_cache[node_key] = neighbor_rows(
                    session,
                    node_key,
                    neighbor_limit,
                    prefer_original,
                )
            return neighbor_cache[node_key]

        return bfs_search(
            start,
            finish["nodeKey"],
            get_neighbors,
            max_depth=max_depth,
            limit=limit,
            max_queue=max_queue,
        )


def neo4j_path_data(path):
    nodes = []
    for node in path.nodes:
        data = dict(node)
        data["labels"] = list(node.labels)
        nodes.append(data)
    return {
        "nodes": nodes,
        "relationships": [dict(relationship) for relationship in path.relationships],
    }


def find_paths_cypher(driver, origin, dest, max_depth=40, limit=10):
    query = route_query(max_depth, limit)
    with driver.session() as session:
        paths = [
            neo4j_path_data(record["p"])
            for record in session.run(
                query,
                origin=origin.strip().upper(),
                dest=dest.strip().upper(),
                limit=limit,
            )
        ]
    return paths, False


def find_paths(driver, origin, dest, max_depth=40, limit=10,
               mode="bfs", neighbor_limit=100, prefer_original=True,
               max_queue=50000):
    if mode == "cypher":
        return find_paths_cypher(driver, origin, dest, max_depth, limit)
    return find_paths_bfs(
        driver,
        origin,
        dest,
        max_depth=max_depth,
        limit=limit,
        neighbor_limit=neighbor_limit,
        prefer_original=prefer_original,
        max_queue=max_queue,
    )


def node_text(node):
    labels = set(node["labels"])
    if "Airport" in labels:
        return f"{node.get('ARPT_ID', '?')} {node.get('ARPT_NAME', '')}".strip()
    if "Fix" in labels:
        return f"{node.get('FIX_ID', '?')} [FIX]"
    return (
        f"{node.get('NAV_ID', '?')} "
        f"[NAVAID: {node.get('NAV_TYPE', '?')}] "
        f"{node.get('NAME', '')}"
    ).strip()


def print_paths(paths, truncated=False):
    if truncated:
        print("搜索队列超过 --max-queue，已提前停止；请减小 max-depth 或提高上限")
    if not paths:
        print("未找到路径")
        return

    for number, path in enumerate(paths, start=1):
        relationships = path["relationships"]
        nodes = path["nodes"]
        print(f"\nPath {number} | hops={len(relationships)}")
        print(node_text(nodes[0]))
        for relationship, node in zip(relationships, nodes[1:]):
            route_keys = relationship.get("sourceRouteKeys") or ""
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
    parser.add_argument("--neighbor-limit", type=int, default=100)
    parser.add_argument("--max-queue", type=int, default=50000)
    parser.add_argument("--mode", choices=("bfs", "cypher"), default="bfs")
    parser.add_argument(
        "--prefer-original",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    args = parser.parse_args()
    if not 1 <= args.max_depth <= 80:
        parser.error("--max-depth 必须在 1 到 80 之间")
    if not 1 <= args.limit <= 100:
        parser.error("--limit 必须在 1 到 100 之间")
    if not 1 <= args.neighbor_limit <= 1000:
        parser.error("--neighbor-limit 必须在 1 到 1000 之间")
    if args.max_queue < 1:
        parser.error("--max-queue 必须大于 0")

    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "password")
    with GraphDatabase.driver(uri, auth=(user, password)) as driver:
        driver.verify_connectivity()
        paths, truncated = find_paths(
            driver,
            args.origin,
            args.dest,
            max_depth=args.max_depth,
            limit=args.limit,
            mode=args.mode,
            neighbor_limit=args.neighbor_limit,
            prefer_original=args.prefer_original,
            max_queue=args.max_queue,
        )
    print_paths(paths, truncated)


if __name__ == "__main__":
    main()
