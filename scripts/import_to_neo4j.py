import argparse
import os
from pathlib import Path
from zipfile import ZipFile

import pandas as pd
from neo4j import GraphDatabase


NODE_FILES = (
    ("clean_airports.csv", "Airport"),
    ("clean_fixes.csv", "Fix"),
    ("clean_navaids.csv", "Navaid"),
)

EXPECTED_COUNTS = {
    "Airport": 427,
    "Fix": 1580,
    "Navaid": 386,
    "ROUTE_EDGE": 13204,
}

CONSTRAINT_QUERIES = (
    "CREATE CONSTRAINT airport_node_key IF NOT EXISTS "
    "FOR (n:Airport) REQUIRE n.nodeKey IS UNIQUE",
    "CREATE CONSTRAINT fix_node_key IF NOT EXISTS "
    "FOR (n:Fix) REQUIRE n.nodeKey IS UNIQUE",
    "CREATE CONSTRAINT navaid_node_key IF NOT EXISTS "
    "FOR (n:Navaid) REQUIRE n.nodeKey IS UNIQUE",
    "CREATE INDEX airport_id IF NOT EXISTS "
    "FOR (n:Airport) ON (n.ARPT_ID)",
)

EDGE_QUERY = (
    "UNWIND $rows AS row "
    "MATCH (a {nodeKey: row.fromNodeKey}) "
    "MATCH (b {nodeKey: row.toNodeKey}) "
    "MERGE (a)-[r:ROUTE_EDGE {edgeKey: row.edgeKey}]->(b) "
    "SET r += row.props"
)


def clean_value(value):
    if pd.isna(value):
        return None
    value = str(value).strip()
    if value.upper() in {"", "NAN", "NONE", "NULL"}:
        return None
    return value


def read_records(path, integer_fields=()):
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    frame.columns = [column.strip() for column in frame.columns]
    records = []
    for source in frame.to_dict("records"):
        record = {}
        for field, value in source.items():
            value = clean_value(value)
            if value is None:
                continue
            record[field] = int(value) if field in integer_fields else value
        records.append(record)
    return records


def batches(rows, size):
    for start in range(0, len(rows), size):
        yield start, rows[start:start + size]


def add_display_name(label, row):
    row = dict(row)
    if label == "Airport":
        row["displayName"] = " ".join(
            value for value in (row.get("ARPT_ID"), row.get("ARPT_NAME"))
            if value
        )
    elif label == "Fix":
        row["displayName"] = row.get("FIX_ID")
    else:
        row["displayName"] = " ".join(
            value for value in (row.get("NAV_ID"), row.get("NAME"))
            if value
        )
    return row


def node_query(label):
    return (
        f"UNWIND $rows AS row "
        f"MERGE (n:{label} {{nodeKey: row.nodeKey}}) "
        f"SET n += row.props"
    )


def ensure_clean_dir(clean_dir):
    clean_dir = Path(clean_dir)
    required = clean_dir / "clean_edges_bidirectional.csv"
    if required.is_file():
        return clean_dir

    candidates = (clean_dir.with_suffix(".zip"), Path("clean.zip"))
    archive_path = next((path for path in candidates if path.is_file()), None)
    if archive_path is None:
        raise FileNotFoundError(f"找不到 {required} 或 clean.zip")

    with ZipFile(archive_path) as archive:
        names = [name for name in archive.namelist() if not name.endswith("/")]
        has_clean_folder = all(
            Path(name).parts and Path(name).parts[0] == clean_dir.name
            for name in names
        )
        destination = clean_dir.parent if has_clean_folder else clean_dir
        destination.mkdir(parents=True, exist_ok=True)
        root = destination.resolve()
        for member in archive.infolist():
            target = (destination / member.filename).resolve()
            if not target.is_relative_to(root):
                raise ValueError(f"ZIP 中存在越界路径：{member.filename}")
        archive.extractall(destination)
    return clean_dir


def run_batches(session, query, rows, batch_size, label):
    loaded = 0
    for start, batch in batches(rows, batch_size):
        try:
            session.run(query, rows=batch).consume()
        except Exception:
            finish = start + len(batch) - 1
            print(f"{label} 批次失败：{start}-{finish}")
            raise
        loaded += len(batch)
        print(f"{label}: {loaded}/{len(rows)}")
    return loaded


def import_graph(driver, clean_dir, reset=False, batch_size=1000):
    clean_dir = ensure_clean_dir(clean_dir)
    counts = {}

    with driver.session() as session:
        if reset:
            session.run("MATCH (n) DETACH DELETE n").consume()

        session.run("DROP CONSTRAINT route_node_key IF EXISTS").consume()
        for query in CONSTRAINT_QUERIES:
            session.run(query).consume()

        for filename, label in NODE_FILES:
            records = [
                add_display_name(label, row)
                for row in read_records(clean_dir / filename)
            ]
            rows = [
                {"nodeKey": row["nodeKey"], "props": row}
                for row in records
                if row.get("nodeKey")
            ]
            counts[label] = run_batches(
                session, node_query(label), rows, batch_size, label
            )

        records = read_records(
            clean_dir / "clean_edges_bidirectional.csv",
            integer_fields={"sourceRouteCount"},
        )
        skipped = sum(
            not row.get("fromNodeKey") or not row.get("toNodeKey")
            for row in records
        )
        rows = [
            {
                "edgeKey": row["edgeKey"],
                "fromNodeKey": row["fromNodeKey"],
                "toNodeKey": row["toNodeKey"],
                "props": row,
            }
            for row in records
            if row.get("edgeKey")
            and row.get("fromNodeKey")
            and row.get("toNodeKey")
        ]
        counts["ROUTE_EDGE"] = run_batches(
            session, EDGE_QUERY, rows, batch_size, "ROUTE_EDGE"
        )
        counts["skipped_edges"] = skipped

        database_counts = {
            "Airport": session.run(
                "MATCH (n:Airport) RETURN count(n) AS count"
            ).single()["count"],
            "Fix": session.run(
                "MATCH (n:Fix) RETURN count(n) AS count"
            ).single()["count"],
            "Navaid": session.run(
                "MATCH (n:Navaid) RETURN count(n) AS count"
            ).single()["count"],
            "ROUTE_EDGE": session.run(
                "MATCH ()-[r:ROUTE_EDGE]->() RETURN count(r) AS count"
            ).single()["count"],
        }

    for name, value in database_counts.items():
        print(f"{name}: {value}")
        if name in EXPECTED_COUNTS and value != EXPECTED_COUNTS[name]:
            print(f"警告：预期约 {EXPECTED_COUNTS[name]}，实际为 {value}")
    if skipped:
        print(f"跳过空端点边：{skipped}")
    return database_counts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--clean-dir", default="data/clean")
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--batch-size", type=int, default=1000)
    args = parser.parse_args()
    if args.batch_size < 1:
        parser.error("--batch-size 必须大于 0")

    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "password")
    with GraphDatabase.driver(uri, auth=(user, password)) as driver:
        driver.verify_connectivity()
        import_graph(
            driver,
            args.clean_dir,
            reset=args.reset,
            batch_size=args.batch_size,
        )


if __name__ == "__main__":
    main()
