import argparse
import csv
import os
from dataclasses import dataclass
from pathlib import Path


DEFAULT_CLEAN_DIR = Path("data/clean")
DEFAULT_URI = "bolt://localhost:7687"
DEFAULT_USER = "neo4j"
DEFAULT_DATABASE = "neo4j"
DEFAULT_BATCH_SIZE = 1000


@dataclass(frozen=True)
class NodeSpec:
    filename: str
    label: str
    key_property: str


@dataclass(frozen=True)
class RelSpec:
    filename: str
    rel_type: str
    from_label: str
    from_key_property: str
    to_label: str | None = None
    to_key_property: str | None = None
    dynamic_target: str | None = None


NODE_SPECS = [
    NodeSpec("clean_airports.csv", "Airport", "airportKey"),
    NodeSpec("clean_runways.csv", "Runway", "runwayKey"),
    NodeSpec("clean_runway_ends.csv", "RunwayEnd", "runwayEndKey"),
    NodeSpec("clean_route_points.csv", "RoutePoint", "pointKey"),
    NodeSpec("clean_airways.csv", "Airway", "airwayKey"),
    NodeSpec("clean_airway_paths.csv", "AirwayPath", "airwayPathKey"),
    NodeSpec("clean_airway_occurrences.csv", "AirwayPointOccurrence", "airwayOccurrenceKey"),
    NodeSpec("clean_procedures.csv", "Procedure", "procedureKey"),
    NodeSpec("clean_procedure_paths.csv", "ProcedurePath", "procedurePathKey"),
    NodeSpec("clean_procedure_occurrences.csv", "ProcedurePointOccurrence", "procedureOccurrenceKey"),
    NodeSpec("clean_route_templates.csv", "RouteTemplate", "templateKey"),
    NodeSpec("clean_template_paths.csv", "TemplatePath", "templatePathKey"),
    NodeSpec("clean_template_tokens.csv", "TemplateTokenOccurrence", "templateTokenKey"),
]


REL_SPECS = [
    RelSpec("rel_airport_has_runway.csv", "HAS_RUNWAY", "Airport", "airportKey", "Runway", "runwayKey"),
    RelSpec("rel_runway_has_runway_end.csv", "HAS_RUNWAY_END", "Runway", "runwayKey", "RunwayEnd", "runwayEndKey"),
    RelSpec("rel_airway_has_path.csv", "HAS_PATH", "Airway", "airwayKey", "AirwayPath", "airwayPathKey"),
    RelSpec("rel_airway_path_has_occurrence.csv", "HAS_OCCURRENCE", "AirwayPath", "airwayPathKey", "AirwayPointOccurrence", "airwayOccurrenceKey"),
    RelSpec("rel_airway_occurrence_resolves_to.csv", "RESOLVES_TO", "AirwayPointOccurrence", "airwayOccurrenceKey", "RoutePoint", "pointKey"),
    RelSpec("rel_next_on_airway.csv", "NEXT_ON_AIRWAY", "AirwayPointOccurrence", "airwayOccurrenceKey", "AirwayPointOccurrence", "airwayOccurrenceKey"),
    RelSpec("rel_procedure_has_path.csv", "HAS_PATH", "Procedure", "procedureKey", "ProcedurePath", "procedurePathKey"),
    RelSpec("rel_procedure_serves_airport.csv", "SERVES_AIRPORT", "Procedure", "procedureKey", "Airport", "airportKey"),
    RelSpec("rel_procedure_path_has_occurrence.csv", "HAS_OCCURRENCE", "ProcedurePath", "procedurePathKey", "ProcedurePointOccurrence", "procedureOccurrenceKey"),
    RelSpec("rel_procedure_occurrence_resolves_to.csv", "RESOLVES_TO", "ProcedurePointOccurrence", "procedureOccurrenceKey", "RoutePoint", "pointKey"),
    RelSpec("rel_next_on_procedure.csv", "NEXT_ON_PROCEDURE", "ProcedurePointOccurrence", "procedureOccurrenceKey", "ProcedurePointOccurrence", "procedureOccurrenceKey"),
    RelSpec("rel_procedure_path_associated_with_runway_end.csv", "ASSOCIATED_WITH_RUNWAY_END", "ProcedurePath", "procedurePathKey", "RunwayEnd", "runwayEndKey"),
    RelSpec("rel_template_has_path.csv", "HAS_PATH", "RouteTemplate", "templateKey", "TemplatePath", "templatePathKey"),
    RelSpec("rel_template_path_has_occurrence.csv", "HAS_OCCURRENCE", "TemplatePath", "templatePathKey", "TemplateTokenOccurrence", "templateTokenKey"),
    RelSpec("rel_next_template_token.csv", "NEXT_TEMPLATE_TOKEN", "TemplateTokenOccurrence", "templateTokenKey", "TemplateTokenOccurrence", "templateTokenKey"),
    RelSpec("rel_template_origin_ref.csv", "ORIGIN_REF", "RouteTemplate", "templateKey", dynamic_target="template_endpoint"),
    RelSpec("rel_template_destination_ref.csv", "DESTINATION_REF", "RouteTemplate", "templateKey", dynamic_target="template_endpoint"),
    RelSpec("rel_template_token_references.csv", "REFERENCES", "TemplateTokenOccurrence", "templateTokenKey", dynamic_target="template_token_reference"),
]


def read_csv_rows(path):
    if not path.exists():
        raise FileNotFoundError(f"Missing clean CSV: {path}")
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def chunks(rows, size):
    for start in range(0, len(rows), size):
        yield rows[start:start + size]


def route_point_labels(row):
    point_type = row.get("pointType", "")
    extra = {
        "FIX": "Fix",
        "NAVAID": "Navaid",
        "BOUNDARY": "BoundaryPoint",
    }.get(point_type)
    if extra:
        return f":RoutePoint:{extra}"
    return ":RoutePoint"


def resolve_template_endpoint(to_key):
    if to_key.startswith("AIRPORT:"):
        return ("Airport", "airportKey", to_key)
    if to_key.startswith("POINT:"):
        return ("RoutePoint", "pointKey", to_key)
    raise ValueError(f"Unsupported template endpoint toKey prefix: {to_key}")


def resolve_template_token_reference(row):
    ref_type = row.get("refType", "")
    to_key = row.get("toKey", "")
    if ref_type == "RoutePoint":
        return ("RoutePoint", "pointKey", to_key)
    if ref_type == "Airway":
        return ("Airway", "airwayKey", to_key)
    if ref_type == "Procedure":
        return ("Procedure", "procedureKey", to_key)
    raise ValueError(f"Unsupported template token refType: {ref_type}")


def target_for_relationship(spec, row):
    if spec.dynamic_target == "template_endpoint":
        return resolve_template_endpoint(row.get("toKey", ""))
    if spec.dynamic_target == "template_token_reference":
        return resolve_template_token_reference(row)
    return (spec.to_label, spec.to_key_property, row.get("toKey", ""))


def contains_forbidden_projection_terms():
    terms = ["ROUTE" + "_EDGE", "TRAVERSE" + "_TO", "USES" + "_"]
    source = Path(__file__).read_text(encoding="utf-8")
    return any(term in source for term in terms)


def with_import_metadata(rows, rel_file):
    prepared = []
    for index, row in enumerate(rows, start=1):
        item = dict(row)
        item["_importRelKey"] = f"{rel_file}:{index}:{row.get('fromKey', '')}->{row.get('toKey', '')}"
        item["_sourceRelFile"] = rel_file
        prepared.append(item)
    return prepared


def node_batches(rows, spec):
    if spec.label != "RoutePoint":
        for batch in chunks(rows, 1_000_000):
            yield f":{spec.label}", batch
        return

    groups = {}
    for row in rows:
        groups.setdefault(route_point_labels(row), []).append(row)
    for labels, group_rows in groups.items():
        yield labels, group_rows


def create_constraints(session):
    for spec in NODE_SPECS:
        name = f"{spec.label.lower()}_{spec.key_property}"
        session.run(
            f"CREATE CONSTRAINT {name} IF NOT EXISTS "
            f"FOR (n:{spec.label}) REQUIRE n.{spec.key_property} IS UNIQUE"
        ).consume()


def reset_database(session):
    session.run("MATCH (n) DETACH DELETE n").consume()


def import_nodes(session, clean_dir, batch_size):
    counts = {}
    for spec in NODE_SPECS:
        rows = read_csv_rows(clean_dir / spec.filename)
        counts[spec.label] = len(rows)
        for labels, label_rows in node_batches(rows, spec):
            for batch in chunks(label_rows, batch_size):
                session.run(
                    f"""
                    UNWIND $rows AS row
                    MERGE (n{labels} {{{spec.key_property}: row.key}})
                    SET n += row.props
                    """,
                    rows=[
                        {
                            "key": row[spec.key_property],
                            "props": dict(row),
                        }
                        for row in batch
                    ],
                ).consume()
    return counts


def import_relationship_group(session, spec, rows, to_label, to_key_property, batch_size):
    for batch in chunks(rows, batch_size):
        session.run(
            f"""
            UNWIND $rows AS row
            MATCH (a:{spec.from_label} {{{spec.from_key_property}: row.fromKey}})
            MATCH (b:{to_label} {{{to_key_property}: row.toKey}})
            MERGE (a)-[r:{spec.rel_type} {{importRelKey: row.importRelKey}}]->(b)
            SET r += row.props
            """,
            rows=[
                {
                    "fromKey": row["fromKey"],
                    "toKey": row["_targetKey"],
                    "importRelKey": row["_importRelKey"],
                    "props": {
                        key: value
                        for key, value in row.items()
                        if not key.startswith("_")
                    } | {
                        "importRelKey": row["_importRelKey"],
                        "sourceRelFile": row["_sourceRelFile"],
                    },
                }
                for row in batch
            ],
        ).consume()


def import_relationships(session, clean_dir, batch_size):
    counts = {}
    for spec in REL_SPECS:
        rows = with_import_metadata(read_csv_rows(clean_dir / spec.filename), spec.filename)
        counts[spec.filename] = (spec.rel_type, len(rows))

        groups = {}
        for row in rows:
            to_label, to_key_property, target_key = target_for_relationship(spec, row)
            row["_targetKey"] = target_key
            groups.setdefault((to_label, to_key_property), []).append(row)

        for (to_label, to_key_property), group_rows in groups.items():
            import_relationship_group(
                session, spec, group_rows, to_label, to_key_property, batch_size
            )
    return counts


def count_nodes(session):
    result = {}
    for spec in NODE_SPECS:
        value = session.run(
            f"MATCH (n:{spec.label}) RETURN count(n) AS count"
        ).single()["count"]
        result[spec.label] = value
    return result


def count_relationship_file(session, rel_type, filename):
    return session.run(
        f"""
        MATCH ()-[r:{rel_type}]->()
        WHERE r.sourceRelFile = $filename
        RETURN count(r) AS count
        """,
        filename=filename,
    ).single()["count"]


def validate_counts(session, node_expected, rel_expected):
    node_actual = count_nodes(session)
    for label, expected in node_expected.items():
        actual = node_actual[label]
        if actual != expected:
            raise RuntimeError(
                f"Node count mismatch for {label}: expected {expected}, actual {actual}"
            )

    rel_actual = {}
    for filename, (rel_type, expected) in rel_expected.items():
        actual = count_relationship_file(session, rel_type, filename)
        rel_actual[filename] = (rel_type, actual)
        if actual != expected:
            raise RuntimeError(
                f"Relationship count mismatch for {filename} ({rel_type}): "
                f"expected {expected}, actual {actual}"
            )
    return node_actual, rel_actual


def load_clean_graph(driver, clean_dir, database, batch_size, reset=True):
    clean_dir = Path(clean_dir)
    with driver.session(database=database) as session:
        if reset:
            reset_database(session)
        create_constraints(session)
        node_expected = import_nodes(session, clean_dir, batch_size)
        rel_expected = import_relationships(session, clean_dir, batch_size)
        node_actual, rel_actual = validate_counts(session, node_expected, rel_expected)
    return node_actual, rel_actual


def print_summary(clean_dir, database, node_counts, rel_counts):
    print(f"Database: {database}")
    print(f"Clean dir: {Path(clean_dir)}")
    print("Nodes:")
    for label in sorted(node_counts):
        print(f"  {label}: {node_counts[label]}")
    print("Relationships:")
    for filename in sorted(rel_counts):
        rel_type, count = rel_counts[filename]
        print(f"  {filename} ({rel_type}): {count}")
    print("Count validation: passed")


def parse_args():
    parser = argparse.ArgumentParser(description="Import NASR v1 clean source facts into Neo4j.")
    parser.add_argument("--clean-dir", default=DEFAULT_CLEAN_DIR, type=Path)
    parser.add_argument("--uri", default=DEFAULT_URI)
    parser.add_argument("--user", default=DEFAULT_USER)
    parser.add_argument("--password", default=os.environ.get("NEO4J_PASSWORD"))
    parser.add_argument("--database", default=DEFAULT_DATABASE)
    parser.add_argument("--batch-size", default=DEFAULT_BATCH_SIZE, type=int)
    parser.add_argument("--no-reset", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    if not args.password:
        raise SystemExit("Neo4j password is required: pass --password or set NEO4J_PASSWORD.")
    if args.batch_size < 1:
        raise SystemExit("--batch-size must be >= 1.")

    try:
        from neo4j import GraphDatabase
    except ImportError as exc:
        raise SystemExit(
            "Missing dependency: install neo4j Python driver with `pip install -r requirements.txt`."
        ) from exc

    driver = GraphDatabase.driver(args.uri, auth=(args.user, args.password))
    try:
        node_counts, rel_counts = load_clean_graph(
            driver,
            args.clean_dir,
            args.database,
            args.batch_size,
            reset=not args.no_reset,
        )
    finally:
        driver.close()

    print_summary(args.clean_dir, args.database, node_counts, rel_counts)


if __name__ == "__main__":
    main()
