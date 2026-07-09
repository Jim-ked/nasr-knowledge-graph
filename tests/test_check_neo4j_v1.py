import unittest

from scripts import check_neo4j_v1


class Neo4jV1CheckScriptTests(unittest.TestCase):
    def test_node_labels_match_v1_source_fact_layer(self):
        self.assertEqual(
            set(check_neo4j_v1.NODE_LABELS),
            {
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
            },
        )

    def test_relationship_types_match_v1_source_fact_layer(self):
        self.assertEqual(
            set(check_neo4j_v1.REL_TYPES),
            {
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
            },
        )

    def test_legacy_projection_terms_are_not_present(self):
        self.assertFalse(check_neo4j_v1.contains_forbidden_projection_terms())


if __name__ == "__main__":
    unittest.main()
