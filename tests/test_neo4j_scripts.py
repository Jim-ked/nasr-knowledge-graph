import unittest

from scripts.import_to_neo4j import batches, clean_value
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


class RouteQueryTests(unittest.TestCase):
    def test_query_uses_only_directed_edges_and_all_limits(self):
        query = route_query(40)

        self.assertIn("-[:ROUTE_EDGE*1..40]->", query)
        self.assertNotIn("-[:ROUTE_EDGE*1..40]-\n", query)
        self.assertIn("single(m IN ns WHERE m = n)", query)
        self.assertIn("none(n IN ns[1..size(ns)-1] WHERE n:Airport)", query)
        self.assertIn("LIMIT $limit", query)

    def test_max_depth_is_validated_before_interpolation(self):
        for value in (0, 81):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    route_query(value)


if __name__ == "__main__":
    unittest.main()
