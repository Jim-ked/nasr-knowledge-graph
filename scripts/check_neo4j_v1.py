import argparse
import os
from pathlib import Path


DEFAULT_URI = "bolt://localhost:7687"
DEFAULT_USER = "neo4j"
DEFAULT_DATABASE = "neo4j"


NODE_LABELS = [
    "Airport",
    "Runway",
    "RunwayEnd",
    "RoutePoint",
    "Fix",
    "Navaid",
    "BoundaryPoint",
    "Airway",
    "AirwayPath",
    "AirwayPointOccurrence",
    "Procedure",
    "ProcedurePath",
    "ProcedurePointOccurrence",
    "RouteTemplate",
    "TemplatePath",
    "TemplateTokenOccurrence",
]


REL_TYPES = [
    "HAS_RUNWAY",
    "HAS_RUNWAY_END",
    "HAS_PATH",
    "HAS_OCCURRENCE",
    "RESOLVES_TO",
    "NEXT_ON_AIRWAY",
    "SERVES_AIRPORT",
    "NEXT_ON_PROCEDURE",
    "ASSOCIATED_WITH_RUNWAY_END",
    "ORIGIN_REF",
    "DESTINATION_REF",
    "NEXT_TEMPLATE_TOKEN",
    "REFERENCES",
]


ORPHAN_CHECKS = [
    ("AirwayPath", "airwayPathKey", "HAS_PATH"),
    ("AirwayPointOccurrence", "airwayOccurrenceKey", "HAS_OCCURRENCE"),
    ("ProcedurePath", "procedurePathKey", "HAS_PATH"),
    ("ProcedurePointOccurrence", "procedureOccurrenceKey", "HAS_OCCURRENCE"),
    ("TemplatePath", "templatePathKey", "HAS_PATH"),
    ("TemplateTokenOccurrence", "templateTokenKey", "HAS_OCCURRENCE"),
]


def contains_forbidden_projection_terms():
    forbidden = ["ROUTE" + "_EDGE", "TRAVERSE" + "_TO", "USES" + "_"]
    source = Path(__file__).read_text(encoding="utf-8")
    return any(term in source for term in forbidden)


def scalar(session, query, **params):
    record = session.run(query, **params).single()
    return record[0] if record else 0


def print_node_counts(session):
    print("Node label counts:")
    for label in NODE_LABELS:
        count = scalar(session, f"MATCH (n:{label}) RETURN count(n)")
        print(f"  {label}: {count}")


def print_relationship_counts(session):
    print("Relationship type counts:")
    for rel_type in REL_TYPES:
        count = scalar(session, f"MATCH ()-[r:{rel_type}]->() RETURN count(r)")
        print(f"  {rel_type}: {count}")


def print_orphan_checks(session):
    print("Orphan key object checks:")
    for label, key_prop, rel_type in ORPHAN_CHECKS:
        query = (
            f"MATCH (n:{label}) "
            f"WHERE NOT ()-[:{rel_type}]->(n) "
            f"RETURN count(n) AS count"
        )
        count = scalar(session, query)
        print(f"  {label} without incoming {rel_type}: {count}")
        if count:
            sample_query = (
                f"MATCH (n:{label}) "
                f"WHERE NOT ()-[:{rel_type}]->(n) "
                f"RETURN n.{key_prop} AS key "
                f"ORDER BY key "
                f"LIMIT 10"
            )
            rows = session.run(sample_query).data()
            for row in rows:
                print(f"    sample: {row['key']}")


def unresolved_occurrence_checks():
    return [
        (
            "AirwayPointOccurrence",
            "airwayOccurrenceKey",
            "resolvedPointKey",
            "coalesce(n.resolvedPointKey, '') = ''",
        ),
        (
            "ProcedurePointOccurrence",
            "procedureOccurrenceKey",
            "resolvedPointKey",
            "coalesce(n.resolvedPointKey, '') = ''",
        ),
        (
            "TemplateTokenOccurrence",
            "templateTokenKey",
            "resolvedRefKey",
            "coalesce(n.resolvedRefKey, '') = '' AND coalesce(n.resolveStatus, '') <> 'unsupported'",
        ),
    ]


def print_unresolved_occurrences(session):
    print("Unresolved occurrence checks:")
    for label, key_prop, value_prop, condition in unresolved_occurrence_checks():
        count = scalar(
            session,
            f"MATCH (n:{label}) WHERE {condition} RETURN count(n) AS count",
        )
        print(f"  {label} with empty {value_prop}: {count}")
        if count:
            rows = session.run(
                f"""
                MATCH (n:{label})
                WHERE {condition}
                RETURN n.{key_prop} AS key,
                       n.resolveStatus AS resolveStatus,
                       n.rawPoint AS rawPoint,
                       n.rawFromPoint AS rawFromPoint,
                       n.segValueRaw AS segValueRaw
                ORDER BY key
                LIMIT 10
                """
            ).data()
            for row in rows:
                raw = row.get("rawPoint") or row.get("rawFromPoint") or row.get("segValueRaw") or ""
                print(
                    f"    sample: {row['key']} | status={row.get('resolveStatus') or ''} | raw={raw}"
                )


def print_airway_samples(session):
    print("AirwayPath samples:")
    rows = session.run(
        """
        MATCH (airway:Airway)-[:HAS_PATH]->(path:AirwayPath)
        OPTIONAL MATCH (path)-[:HAS_OCCURRENCE]->(occ:AirwayPointOccurrence)
        WITH airway, path, occ
        ORDER BY path.airwayPathKey, toInteger(occ.pointSeq), occ.airwayOccurrenceKey
        WITH airway, path, collect(occ)[0..5] AS occurrences
        RETURN airway.airwayKey AS airwayKey,
               path.airwayPathKey AS pathKey,
               [o IN occurrences | o.airwayOccurrenceKey + ':' + coalesce(o.rawFromPoint, '')] AS occurrenceKeys
        ORDER BY pathKey
        LIMIT 5
        """
    ).data()
    for row in rows:
        print(f"  {row['pathKey']} <- {row['airwayKey']}")
        for item in row["occurrenceKeys"]:
            print(f"    {item}")


def print_procedure_samples(session):
    print("ProcedurePath samples:")
    rows = session.run(
        """
        MATCH (procedure:Procedure)-[:HAS_PATH]->(path:ProcedurePath)
        OPTIONAL MATCH (path)-[:HAS_OCCURRENCE]->(occ:ProcedurePointOccurrence)
        WITH procedure, path, occ
        ORDER BY path.procedurePathKey, toInteger(occ.pointSeq), occ.procedureOccurrenceKey
        WITH procedure, path, collect(occ)[0..5] AS occurrences
        RETURN procedure.procedureKey AS procedureKey,
               path.procedurePathKey AS pathKey,
               [o IN occurrences | o.procedureOccurrenceKey + ':' + coalesce(o.rawPoint, '')] AS occurrenceKeys
        ORDER BY pathKey
        LIMIT 5
        """
    ).data()
    for row in rows:
        print(f"  {row['pathKey']} <- {row['procedureKey']}")
        for item in row["occurrenceKeys"]:
            print(f"    {item}")


def print_template_samples(session):
    print("RouteTemplate samples:")
    rows = session.run(
        """
        MATCH (template:RouteTemplate)-[:HAS_PATH]->(path:TemplatePath)
        OPTIONAL MATCH (path)-[:HAS_OCCURRENCE]->(token:TemplateTokenOccurrence)
        WITH template, path, token
        ORDER BY template.templateKey, path.templatePathKey, toInteger(token.segmentSeq), token.templateTokenKey
        WITH template, path, collect(token)[0..10] AS tokens
        RETURN template.templateKey AS templateKey,
               path.templatePathKey AS pathKey,
               [t IN tokens | t.templateTokenKey + ':' + coalesce(t.segValueRaw, '') + ':' + coalesce(t.resolveStatus, '')] AS tokenKeys
        ORDER BY templateKey
        LIMIT 5
        """
    ).data()
    for row in rows:
        print(f"  {row['templateKey']} -> {row['pathKey']}")
        for item in row["tokenKeys"]:
            print(f"    {item}")


def run_checks(driver, database):
    with driver.session(database=database) as session:
        print(f"Database: {database}")
        print_node_counts(session)
        print_relationship_counts(session)
        print_orphan_checks(session)
        print_unresolved_occurrences(session)
        print_airway_samples(session)
        print_procedure_samples(session)
        print_template_samples(session)


def parse_args():
    parser = argparse.ArgumentParser(description="Check Neo4j NASR v1 source fact import.")
    parser.add_argument("--uri", default=DEFAULT_URI)
    parser.add_argument("--user", default=DEFAULT_USER)
    parser.add_argument("--password", default=os.environ.get("NEO4J_PASSWORD"))
    parser.add_argument("--database", default=DEFAULT_DATABASE)
    return parser.parse_args()


def main():
    args = parse_args()
    if not args.password:
        raise SystemExit("Neo4j password is required: pass --password or set NEO4J_PASSWORD.")

    try:
        from neo4j import GraphDatabase
    except ImportError as exc:
        raise SystemExit(
            "Missing dependency: install neo4j Python driver with `pip install -r requirements.txt`."
        ) from exc

    driver = GraphDatabase.driver(args.uri, auth=(args.user, args.password))
    try:
        run_checks(driver, args.database)
    finally:
        driver.close()


if __name__ == "__main__":
    main()
