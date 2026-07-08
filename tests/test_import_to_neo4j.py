import unittest

from scripts import import_to_neo4j


class Neo4jImportMappingTests(unittest.TestCase):
    def test_csv_mappings_cover_v1_clean_files(self):
        node_files = {spec.filename for spec in import_to_neo4j.NODE_SPECS}
        rel_files = {spec.filename for spec in import_to_neo4j.REL_SPECS}

        self.assertEqual(
            node_files,
            {
                "clean_airports.csv",
                "clean_runways.csv",
                "clean_runway_ends.csv",
                "clean_route_points.csv",
                "clean_airways.csv",
                "clean_airway_paths.csv",
                "clean_airway_occurrences.csv",
                "clean_procedures.csv",
                "clean_procedure_paths.csv",
                "clean_procedure_occurrences.csv",
                "clean_route_templates.csv",
                "clean_template_paths.csv",
                "clean_template_tokens.csv",
            },
        )
        self.assertEqual(
            rel_files,
            {
                "rel_airport_has_runway.csv",
                "rel_runway_has_runway_end.csv",
                "rel_airway_has_path.csv",
                "rel_airway_path_has_occurrence.csv",
                "rel_airway_occurrence_resolves_to.csv",
                "rel_next_on_airway.csv",
                "rel_procedure_has_path.csv",
                "rel_procedure_serves_airport.csv",
                "rel_procedure_path_has_occurrence.csv",
                "rel_procedure_occurrence_resolves_to.csv",
                "rel_next_on_procedure.csv",
                "rel_procedure_path_associated_with_runway_end.csv",
                "rel_template_has_path.csv",
                "rel_template_path_has_occurrence.csv",
                "rel_next_template_token.csv",
                "rel_template_origin_ref.csv",
                "rel_template_destination_ref.csv",
                "rel_template_token_references.csv",
            },
        )

    def test_template_origin_and_destination_ref_split_by_to_key_prefix(self):
        airport = import_to_neo4j.resolve_template_endpoint("AIRPORT:ATL")
        point = import_to_neo4j.resolve_template_endpoint("POINT:FIX:BURGG:K7")

        self.assertEqual(airport, ("Airport", "airportKey", "AIRPORT:ATL"))
        self.assertEqual(point, ("RoutePoint", "pointKey", "POINT:FIX:BURGG:K7"))

        with self.assertRaisesRegex(ValueError, "Unsupported template endpoint"):
            import_to_neo4j.resolve_template_endpoint("AIRWAY:J1")

    def test_template_token_reference_split_by_ref_type(self):
        self.assertEqual(
            import_to_neo4j.resolve_template_token_reference(
                {"toKey": "POINT:FIX:BURGG:K7", "refType": "RoutePoint"}
            ),
            ("RoutePoint", "pointKey", "POINT:FIX:BURGG:K7"),
        )
        self.assertEqual(
            import_to_neo4j.resolve_template_token_reference(
                {"toKey": "AIRWAY:J1", "refType": "Airway"}
            ),
            ("Airway", "airwayKey", "AIRWAY:J1"),
        )
        self.assertEqual(
            import_to_neo4j.resolve_template_token_reference(
                {"toKey": "PROCEDURE:DP:ABC", "refType": "Procedure"}
            ),
            ("Procedure", "procedureKey", "PROCEDURE:DP:ABC"),
        )

        with self.assertRaisesRegex(ValueError, "Unsupported template token refType"):
            import_to_neo4j.resolve_template_token_reference(
                {"toKey": "AIRPORT:ATL", "refType": "Airport"}
            )

    def test_legacy_projection_terms_are_not_present(self):
        self.assertFalse(import_to_neo4j.contains_forbidden_projection_terms())


if __name__ == "__main__":
    unittest.main()
