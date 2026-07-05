import unittest

from scripts.import_to_neo4j import (
    CONSTRAINT_QUERIES,
    EDGE_QUERY,
    add_display_name,
    batches,
    clean_value,
    node_query,
)
from scripts.query_route import route_query


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

        self.assertEqual(airport["displayName"], "ATL Atlanta")
        self.assertEqual(fix["displayName"], "BURGG")
        self.assertEqual(navaid["displayName"], "HNN Henderson")
        for label in ("Airport", "Fix", "Navaid"):
            query = node_query(label)
            self.assertIn(f"MERGE (n:{label} ", query)
            self.assertNotIn("RouteNode", query)

    def test_schema_and_edges_do_not_use_route_node(self):
        schema = " ".join(CONSTRAINT_QUERIES)

        self.assertIn("airport_node_key", schema)
        self.assertIn("fix_node_key", schema)
        self.assertIn("navaid_node_key", schema)
        self.assertNotIn("FOR (n:RouteNode)", schema)
        self.assertIn("MATCH (a {nodeKey: row.fromNodeKey})", EDGE_QUERY)
        self.assertIn("MATCH (b {nodeKey: row.toNodeKey})", EDGE_QUERY)
        self.assertNotIn(":RouteNode", EDGE_QUERY)


class RouteQueryTests(unittest.TestCase):
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
