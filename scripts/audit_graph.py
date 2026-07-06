import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase


load_dotenv(Path(__file__).resolve().parents[1] / ".env")


NODE_LABELS = (
    "Airport",
    "Fix",
    "Navaid",
    "PreferredRoute",
    "RouteSegment",
    "Airway",
    "Procedure",
)

RELATIONSHIP_TYPES = (
    "ROUTE_EDGE",
    "ORIGIN_OF",
    "DESTINATION_AIRPORT",
    "HAS_SEGMENT",
    "NEXT_SEGMENT",
    "REFERENCES",
    "USES_AIRWAY",
    "USES_PROCEDURE",
)


def rows(session, query):
    return [record.data() for record in session.run(query)]


def audit_graph(driver):
    report = {}
    with driver.session() as session:
        report["nodeCounts"] = {
            label: session.run(
                f"MATCH (n:{label}) RETURN count(n) AS count"
            ).single()["count"]
            for label in NODE_LABELS
        }
        report["relationshipCounts"] = {
            relation: session.run(
                f"MATCH ()-[r:{relation}]->() RETURN count(r) AS count"
            ).single()["count"]
            for relation in RELATIONSHIP_TYPES
        }
        report["isolatedNodeCount"] = session.run(
            "MATCH (n) WHERE NOT (n)--() RETURN count(n) AS count"
        ).single()["count"]
        report["isolatedAirports"] = rows(
            session,
            "MATCH (a:Airport) WHERE NOT (a)--() "
            "RETURN a.ARPT_ID AS airportId, a.ARPT_NAME AS airportName "
            "ORDER BY airportId",
        )
        report["airportsWithFewestRouteNeighbors"] = rows(
            session,
            "MATCH (a:Airport) "
            "OPTIONAL MATCH (a)-[:ROUTE_EDGE]-(n) "
            "RETURN a.ARPT_ID AS airportId, a.ARPT_NAME AS airportName, "
            "count(DISTINCT n) AS uniqueNeighbors, "
            "COUNT { (a)-[:ROUTE_EDGE]->() } AS outDegree, "
            "COUNT { ()-[:ROUTE_EDGE]->(a) } AS inDegree "
            "ORDER BY uniqueNeighbors ASC, airportId "
            "LIMIT 50",
        )
        report["airportsWithFewestPreferredRoutes"] = rows(
            session,
            "MATCH (a:Airport) "
            "OPTIONAL MATCH (a)-[:ORIGIN_OF]->(r:PreferredRoute) "
            "RETURN a.ARPT_ID AS airportId, a.ARPT_NAME AS airportName, "
            "count(r) AS originRouteCount "
            "ORDER BY originRouteCount ASC, airportId "
            "LIMIT 50",
        )
        report["routeSegmentResolveStatuses"] = rows(
            session,
            "MATCH (s:RouteSegment) "
            "RETURN s.resolveStatus AS resolveStatus, count(*) AS count "
            "ORDER BY count DESC",
        )
        report["routeSegmentTypes"] = rows(
            session,
            "MATCH (s:RouteSegment) "
            "RETURN s.segmentType AS segmentType, count(*) AS count "
            "ORDER BY count DESC",
        )
        report["searchProjectionStatuses"] = rows(
            session,
            "MATCH (r:PreferredRoute) "
            "RETURN r.searchProjectionStatus AS searchProjectionStatus, "
            "count(*) AS count ORDER BY count DESC",
        )
        report["routeEdgesWithMostSources"] = rows(
            session,
            "MATCH (a)-[r:ROUTE_EDGE]->(b) "
            "RETURN a.nodeKey AS fromNodeKey, b.nodeKey AS toNodeKey, "
            "r.edgeKey AS edgeKey, r.sourceRouteCount AS sourceRouteCount "
            "ORDER BY sourceRouteCount DESC, edgeKey "
            "LIMIT 30",
        )
    return report


def print_report(report):
    print(json.dumps(report, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--export")
    args = parser.parse_args()

    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "password")
    with GraphDatabase.driver(uri, auth=(user, password)) as driver:
        driver.verify_connectivity()
        report = audit_graph(driver)

    print_report(report)
    if args.export:
        output = Path(args.export)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
