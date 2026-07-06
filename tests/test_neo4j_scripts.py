import unittest

from scripts.import_to_neo4j import (
    CONSTRAINT_QUERIES,
    HAS_SEGMENT_QUERY,
    REFERENCES_QUERY,
    USES_AIRWAY_QUERY,
    USES_PROCEDURE_QUERY,
    add_display_name,
    batches,
    clean_value,
    edge_query,
    node_query,
)
from scripts.query_route import (
    NEIGHBOR_QUERY_ORIGINAL_FIRST,
    bfs_search,
    route_query,
)


class ImportHelpersTests(unittest.TestCase):
    def test_empty_database_values_become_none(self):
        for value in ("", "  ", "nan", "None", "NULL", None):
            with self.subTest(value=value):
                self.assertIsNone(clean_value(value))

    def test_batches_preserve_start_positions(self):
        self.assertEqual(
            list(batches([1, 2, 3, 4, 5], 2)),
            [(0, [1, 2]), (2, [3, 4]), (4, [5])],
        )

    def test_nodes_have_specific_labels_and_display_names(self):
        airport = add_display_name(
            "Airport", {"ARPT_ID": "ATL", "ARPT_NAME": "Atlanta"}
        )
        fix = add_display_name("Fix", {"FIX_ID": "BURGG"})
        navaid = add_display_name(
            "Navaid", {"NAV_ID": "HNN", "NAME": "Henderson"}
        )
        route = add_display_name(
            "PreferredRoute",
            {
                "ORIGIN_ID": "ATL",
                "DSTN_ID": "LAX",
                "PFR_TYPE_CODE": "H",
                "ROUTE_NO": "1",
            },
        )
        segment = add_display_name(
            "RouteSegment", {"segmentType": "AIRWAY", "rawValue": "J6"}
        )

        self.assertEqual(airport["displayName"], "ATL Atlanta")
        self.assertEqual(fix["displayName"], "BURGG")
        self.assertEqual(navaid["displayName"], "HNN Henderson")
        self.assertEqual(route["displayName"], "ATL->LAX H:1")
        self.assertEqual(segment["displayName"], "AIRWAY:J6")
        for label, key in (
            ("Airport", "nodeKey"),
            ("Fix", "nodeKey"),
            ("Navaid", "nodeKey"),
            ("PreferredRoute", "routeKey"),
            ("RouteSegment", "segmentKey"),
            ("Airway", "airwayKey"),
            ("Procedure", "procedureKey"),
        ):
            query = node_query(label, key)
            self.assertIn(f"MERGE (n:{label} ", query)
            self.assertNotIn("RouteNode", query)

    def test_schema_and_edges_do_not_use_route_node(self):
        schema = " ".join(CONSTRAINT_QUERIES)

        self.assertIn("airport_node_key", schema)
        self.assertIn("fix_node_key", schema)
        self.assertIn("navaid_node_key", schema)
        self.assertIn("preferred_route_key", schema)
        self.assertIn("route_segment_key", schema)
        self.assertIn("airway_key", schema)
        self.assertIn("procedure_key", schema)
        self.assertNotIn("FOR (n:RouteNode)", schema)
        query = edge_query("Airport", "Fix")
        self.assertIn("MATCH (a:Airport {nodeKey: row.fromNodeKey})", query)
        self.assertIn("MATCH (b:Fix {nodeKey: row.toNodeKey})", query)
        self.assertNotIn(":RouteNode", query)
        self.assertIn("MERGE (r)-[:HAS_SEGMENT", HAS_SEGMENT_QUERY)
        self.assertIn("MERGE (s)-[:REFERENCES]->(n)", REFERENCES_QUERY)
        self.assertIn("MERGE (s)-[:USES_AIRWAY]->(n)", USES_AIRWAY_QUERY)
        self.assertIn("MERGE (s)-[:USES_PROCEDURE]->(n)", USES_PROCEDURE_QUERY)


class RouteQueryTests(unittest.TestCase):
    def test_bfs_enforces_direction_cycles_airports_depth_and_limit(self):
        start = {"nodeKey": "AIRPORT:A", "labels": ["Airport"]}
        graph = {
            "AIRPORT:A": [
                ({"nodeKey": "FIX:X", "labels": ["Fix"]}, {"edgeKey": "A-X"}),
            ],
            "FIX:X": [
                (start, {"edgeKey": "X-A"}),
                (
                    {"nodeKey": "AIRPORT:C", "labels": ["Airport"]},
                    {"edgeKey": "X-C"},
                ),
                (
                    {"nodeKey": "AIRPORT:B", "labels": ["Airport"]},
                    {"edgeKey": "X-B"},
                ),
                ({"nodeKey": "FIX:Y", "labels": ["Fix"]}, {"edgeKey": "X-Y"}),
            ],
            "FIX:Y": [
                (
                    {"nodeKey": "AIRPORT:B", "labels": ["Airport"]},
                    {"edgeKey": "Y-B"},
                ),
            ],
        }

        paths, truncated = bfs_search(
            start,
            "AIRPORT:B",
            lambda key: graph.get(key, []),
            max_depth=3,
            limit=2,
            max_queue=20,
        )

        self.assertFalse(truncated)
        self.assertEqual(
            [[node["nodeKey"] for node in path["nodes"]] for path in paths],
            [
                ["AIRPORT:A", "FIX:X", "AIRPORT:B"],
                ["AIRPORT:A", "FIX:X", "FIX:Y", "AIRPORT:B"],
            ],
        )

    def test_bfs_stops_when_queue_limit_is_reached(self):
        start = {"nodeKey": "AIRPORT:A", "labels": ["Airport"]}
        neighbors = [
            ({"nodeKey": f"FIX:{number}", "labels": ["Fix"]}, {})
            for number in range(3)
        ]

        paths, truncated = bfs_search(
            start,
            "AIRPORT:B",
            lambda key: neighbors if key == "AIRPORT:A" else [],
            max_depth=3,
            limit=10,
            max_queue=2,
        )

        self.assertEqual(paths, [])
        self.assertTrue(truncated)

    def test_neighbor_query_is_directed_ranked_and_limited(self):
        self.assertIn("-[r:ROUTE_EDGE]->(m)", NEIGHBOR_QUERY_ORIGINAL_FIRST)
        self.assertIn("WHEN 'original' THEN 0", NEIGHBOR_QUERY_ORIGINAL_FIRST)
        self.assertIn("LIMIT $neighborLimit", NEIGHBOR_QUERY_ORIGINAL_FIRST)

    def test_query_uses_only_directed_edges_and_all_limits(self):
        query = route_query(40, 10)

        self.assertIn("MATCH SHORTEST 10", query)
        self.assertIn("-[:ROUTE_EDGE*1..40]->", query)
        self.assertNotIn("-[:ROUTE_EDGE*1..40]-\n", query)
        self.assertIn("single(m IN nodes(p) WHERE m = n)", query)
        self.assertIn("none(n IN nodes(p)[1..size(nodes(p))-1]", query)
        self.assertIn("LIMIT $limit", query)

    def test_max_depth_is_validated_before_interpolation(self):
        for value in (0, 81):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    route_query(value, 10)

    def test_limit_is_validated_before_interpolation(self):
        for value in (0, 101):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    route_query(40, value)


if __name__ == "__main__":
    unittest.main()
