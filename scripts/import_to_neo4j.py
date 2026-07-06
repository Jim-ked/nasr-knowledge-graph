import argparse
import os
from pathlib import Path
from zipfile import ZipFile

import pandas as pd
from neo4j import GraphDatabase
from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parents[1] / ".env")


NODE_FILES = (
    ("clean_airports.csv", "Airport", "nodeKey", ()),
    ("clean_fixes.csv", "Fix", "nodeKey", ()),
    ("clean_navaids.csv", "Navaid", "nodeKey", ()),
    ("clean_preferred_routes.csv", "PreferredRoute", "routeKey", ()),
    (
        "clean_route_segments.csv",
        "RouteSegment",
        "segmentKey",
        ("segmentSeq",),
    ),
    (
        "clean_airways.csv",
        "Airway",
        "airwayKey",
        ("sourceSegmentCount",),
    ),
    (
        "clean_procedures.csv",
        "Procedure",
        "procedureKey",
        ("sourceSegmentCount",),
    ),
)

EXPECTED_COUNTS = {
    "Airport": 427,
    "Fix": 1580,
    "Navaid": 386,
    "PreferredRoute": 10769,
    "RouteSegment": 61424,
    "Airway": 371,
    "Procedure": 584,
    "ROUTE_EDGE": 13204,
}

CONSTRAINT_QUERIES = (
    "CREATE CONSTRAINT airport_node_key IF NOT EXISTS "
    "FOR (n:Airport) REQUIRE n.nodeKey IS UNIQUE",
    "CREATE CONSTRAINT fix_node_key IF NOT EXISTS "
    "FOR (n:Fix) REQUIRE n.nodeKey IS UNIQUE",
    "CREATE CONSTRAINT navaid_node_key IF NOT EXISTS "
    "FOR (n:Navaid) REQUIRE n.nodeKey IS UNIQUE",
    "CREATE CONSTRAINT preferred_route_key IF NOT EXISTS "
    "FOR (n:PreferredRoute) REQUIRE n.routeKey IS UNIQUE",
    "CREATE CONSTRAINT route_segment_key IF NOT EXISTS "
    "FOR (n:RouteSegment) REQUIRE n.segmentKey IS UNIQUE",
    "CREATE CONSTRAINT airway_key IF NOT EXISTS "
    "FOR (n:Airway) REQUIRE n.airwayKey IS UNIQUE",
    "CREATE CONSTRAINT procedure_key IF NOT EXISTS "
    "FOR (n:Procedure) REQUIRE n.procedureKey IS UNIQUE",
    "CREATE INDEX airport_id IF NOT EXISTS "
    "FOR (n:Airport) ON (n.ARPT_ID)",
)

ROUTE_NODE_LABELS = {"Airport", "Fix", "Navaid"}


def edge_query(from_label, to_label):
    if from_label not in ROUTE_NODE_LABELS or to_label not in ROUTE_NODE_LABELS:
        raise ValueError("ROUTE_EDGE 端点类型无效")
    return (
        "UNWIND $rows AS row "
        f"MATCH (a:{from_label} {{nodeKey: row.fromNodeKey}}) "
        f"MATCH (b:{to_label} {{nodeKey: row.toNodeKey}}) "
        "MERGE (a)-[r:ROUTE_EDGE {edgeKey: row.edgeKey}]->(b) "
        "SET r += row.props"
    )

ORIGIN_QUERY = (
    "UNWIND $rows AS row "
    "MATCH (a:Airport {ARPT_ID: row.airportId}) "
    "MATCH (r:PreferredRoute {routeKey: row.routeKey}) "
    "MERGE (a)-[:ORIGIN_OF]->(r)"
)

DESTINATION_QUERY = (
    "UNWIND $rows AS row "
    "MATCH (r:PreferredRoute {routeKey: row.routeKey}) "
    "MATCH (a:Airport {ARPT_ID: row.airportId}) "
    "MERGE (r)-[:DESTINATION_AIRPORT]->(a)"
)

HAS_SEGMENT_QUERY = (
    "UNWIND $rows AS row "
    "MATCH (r:PreferredRoute {routeKey: row.routeKey}) "
    "MATCH (s:RouteSegment {segmentKey: row.segmentKey}) "
    "MERGE (r)-[:HAS_SEGMENT {seq: row.seq}]->(s)"
)

NEXT_SEGMENT_QUERY = (
    "UNWIND $rows AS row "
    "MATCH (a:RouteSegment {segmentKey: row.fromSegmentKey}) "
    "MATCH (b:RouteSegment {segmentKey: row.toSegmentKey}) "
    "MERGE (a)-[:NEXT_SEGMENT]->(b)"
)

REFERENCES_QUERY = (
    "UNWIND $rows AS row "
    "MATCH (s:RouteSegment {segmentKey: row.segmentKey}) "
    "MATCH (n {nodeKey: row.resolvedNodeKey}) "
    "WHERE n:Fix OR n:Navaid "
    "MERGE (s)-[:REFERENCES]->(n)"
)

USES_AIRWAY_QUERY = (
    "UNWIND $rows AS row "
    "MATCH (s:RouteSegment {segmentKey: row.segmentKey}) "
    "MATCH (n:Airway {airwayKey: row.resolvedNodeKey}) "
    "MERGE (s)-[:USES_AIRWAY]->(n)"
)

USES_PROCEDURE_QUERY = (
    "UNWIND $rows AS row "
    "MATCH (s:RouteSegment {segmentKey: row.segmentKey}) "
    "MATCH (n:Procedure {procedureKey: row.resolvedNodeKey}) "
    "MERGE (s)-[:USES_PROCEDURE]->(n)"
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
    elif label == "Navaid":
        row["displayName"] = " ".join(
            value for value in (row.get("NAV_ID"), row.get("NAME"))
            if value
        )
    elif label == "PreferredRoute":
        route_type = ":".join(
            value
            for value in (row.get("PFR_TYPE_CODE"), row.get("ROUTE_NO"))
            if value
        )
        row["displayName"] = (
            f"{row.get('ORIGIN_ID', '')}->{row.get('DSTN_ID', '')} "
            f"{route_type}"
        ).strip()
    elif label == "RouteSegment":
        row["displayName"] = (
            f"{row.get('segmentType', '')}:{row.get('rawValue', '')}"
        )
    elif label == "Airway":
        row["displayName"] = row.get("airwayId")
    elif label == "Procedure":
        row["displayName"] = (
            f"{row.get('procedureType', '')}:{row.get('procedureId', '')}"
        )
    return row


def node_query(label, key_field):
    return (
        f"UNWIND $rows AS row "
        f"MERGE (n:{label} {{{key_field}: row.key}}) "
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

        for filename, label, key_field, integer_fields in NODE_FILES:
            records = [
                add_display_name(label, row)
                for row in read_records(
                    clean_dir / filename,
                    integer_fields=set(integer_fields),
                )
            ]
            rows = [
                {"key": row[key_field], "props": row}
                for row in records
                if row.get(key_field)
            ]
            counts[label] = run_batches(
                session,
                node_query(label, key_field),
                rows,
                batch_size,
                label,
            )

        route_records = read_records(
            clean_dir / "clean_preferred_routes.csv"
        )
        origin_rows = [
            {"routeKey": row["routeKey"], "airportId": row["ORIGIN_ID"]}
            for row in route_records
        ]
        destination_rows = [
            {"routeKey": row["routeKey"], "airportId": row["DSTN_ID"]}
            for row in route_records
        ]
        counts["ORIGIN_OF"] = run_batches(
            session, ORIGIN_QUERY, origin_rows, batch_size, "ORIGIN_OF"
        )
        counts["DESTINATION_AIRPORT"] = run_batches(
            session,
            DESTINATION_QUERY,
            destination_rows,
            batch_size,
            "DESTINATION_AIRPORT",
        )

        segment_records = read_records(
            clean_dir / "clean_route_segments.csv",
            integer_fields={"segmentSeq"},
        )
        has_segment_rows = [
            {
                "routeKey": row["routeKey"],
                "segmentKey": row["segmentKey"],
                "seq": row["segmentSeq"],
            }
            for row in segment_records
        ]
        counts["HAS_SEGMENT"] = run_batches(
            session,
            HAS_SEGMENT_QUERY,
            has_segment_rows,
            batch_size,
            "HAS_SEGMENT",
        )

        segments_by_route = {}
        for row in segment_records:
            segments_by_route.setdefault(row["routeKey"], []).append(row)
        next_segment_rows = []
        for segments in segments_by_route.values():
            ordered = sorted(segments, key=lambda row: row["segmentSeq"])
            next_segment_rows.extend(
                {
                    "fromSegmentKey": first["segmentKey"],
                    "toSegmentKey": second["segmentKey"],
                }
                for first, second in zip(ordered, ordered[1:])
            )
        counts["NEXT_SEGMENT"] = run_batches(
            session,
            NEXT_SEGMENT_QUERY,
            next_segment_rows,
            batch_size,
            "NEXT_SEGMENT",
        )

        reference_rows = [
            {
                "segmentKey": row["segmentKey"],
                "resolvedNodeKey": row["resolvedNodeKey"],
            }
            for row in segment_records
            if row.get("resolvedEntityType") in {"Fix", "Navaid"}
            and row.get("resolvedNodeKey")
        ]
        counts["REFERENCES"] = run_batches(
            session,
            REFERENCES_QUERY,
            reference_rows,
            batch_size,
            "REFERENCES",
        )
        airway_rows = [
            {
                "segmentKey": row["segmentKey"],
                "resolvedNodeKey": row["resolvedNodeKey"],
            }
            for row in segment_records
            if row.get("resolvedEntityType") == "Airway"
            and row.get("resolvedNodeKey")
        ]
        counts["USES_AIRWAY"] = run_batches(
            session,
            USES_AIRWAY_QUERY,
            airway_rows,
            batch_size,
            "USES_AIRWAY",
        )
        procedure_rows = [
            {
                "segmentKey": row["segmentKey"],
                "resolvedNodeKey": row["resolvedNodeKey"],
            }
            for row in segment_records
            if row.get("resolvedEntityType") == "Procedure"
            and row.get("resolvedNodeKey")
        ]
        counts["USES_PROCEDURE"] = run_batches(
            session,
            USES_PROCEDURE_QUERY,
            procedure_rows,
            batch_size,
            "USES_PROCEDURE",
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
        edge_groups = {}
        for row in rows:
            source = row["props"]
            pair = (source["fromType"], source["toType"])
            edge_groups.setdefault(pair, []).append(row)
        counts["ROUTE_EDGE"] = 0
        for (from_label, to_label), group in sorted(edge_groups.items()):
            counts["ROUTE_EDGE"] += run_batches(
                session,
                edge_query(from_label, to_label),
                group,
                batch_size,
                f"ROUTE_EDGE {from_label}->{to_label}",
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
            "PreferredRoute": session.run(
                "MATCH (n:PreferredRoute) RETURN count(n) AS count"
            ).single()["count"],
            "RouteSegment": session.run(
                "MATCH (n:RouteSegment) RETURN count(n) AS count"
            ).single()["count"],
            "Airway": session.run(
                "MATCH (n:Airway) RETURN count(n) AS count"
            ).single()["count"],
            "Procedure": session.run(
                "MATCH (n:Procedure) RETURN count(n) AS count"
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
