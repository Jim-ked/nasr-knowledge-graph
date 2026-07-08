import csv
import tempfile
import unittest
from pathlib import Path

from scripts.build_clean_graph_data import build_clean_graph_data


def write_csv(path, columns, rows):
    with path.open("w", encoding="cp1252", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path):
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


class CleanGraphDataTests(unittest.TestCase):
    def test_builds_source_fact_csvs_and_audit_outputs(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            raw = root / "raw"
            clean = root / "clean"
            audit = root / "audit"
            raw.mkdir()

            write_csv(
                raw / "APT_BASE.csv",
                ["ARPT_ID", "ARPT_NAME", "CITY", "STATE_CODE", "COUNTRY_CODE"],
                [
                    {
                        "ARPT_ID": "AAA", "ARPT_NAME": "Alpha",
                        "CITY": "Alpha City", "STATE_CODE": "AA",
                        "COUNTRY_CODE": "US",
                    },
                    {
                        "ARPT_ID": "BBB", "ARPT_NAME": "Beta",
                        "CITY": "Beta City", "STATE_CODE": "BB",
                        "COUNTRY_CODE": "US",
                    },
                    {
                        "ARPT_ID": "0.00E+00", "ARPT_NAME": "Bad",
                        "CITY": "Bad", "STATE_CODE": "ZZ",
                        "COUNTRY_CODE": "US",
                    },
                    {
                        "ARPT_ID": "0.00E+00", "ARPT_NAME": "Bad Two",
                        "CITY": "Bad", "STATE_CODE": "ZZ",
                        "COUNTRY_CODE": "US",
                    },
                ],
            )
            write_csv(
                raw / "APT_RWY.csv",
                ["ARPT_ID", "RWY_ID", "RWY_LEN", "RWY_WIDTH"],
                [{"ARPT_ID": "AAA", "RWY_ID": "09/27", "RWY_LEN": "1000"}],
            )
            write_csv(
                raw / "APT_RWY_END.csv",
                ["ARPT_ID", "RWY_ID", "RWY_END_ID", "TRUE_ALIGNMENT"],
                [{"ARPT_ID": "AAA", "RWY_ID": "09/27", "RWY_END_ID": "09"}],
            )
            write_csv(
                raw / "FIX_BASE.csv",
                ["FIX_ID", "ICAO_REGION_CODE", "LAT_DECIMAL", "LONG_DECIMAL"],
                [{"FIX_ID": "FIXA", "ICAO_REGION_CODE": "K1"}],
            )
            write_csv(
                raw / "NAV_BASE.csv",
                [
                    "NAV_ID", "NAV_TYPE", "NAME", "CITY", "STATE_CODE",
                    "COUNTRY_CODE", "LAT_DECIMAL", "LONG_DECIMAL",
                ],
                [
                    {
                        "NAV_ID": "AA", "NAV_TYPE": "NDB", "NAME": "One",
                        "CITY": "One City", "STATE_CODE": "ND",
                        "COUNTRY_CODE": "US", "LAT_DECIMAL": "1",
                        "LONG_DECIMAL": "2",
                    },
                    {
                        "NAV_ID": "AA", "NAV_TYPE": "NDB", "NAME": "Two",
                        "CITY": "Two City", "STATE_CODE": "GA",
                        "COUNTRY_CODE": "US", "LAT_DECIMAL": "3",
                        "LONG_DECIMAL": "4",
                    },
                ],
            )
            write_csv(
                raw / "AWY_BASE.csv",
                [
                    "AWY_ID", "AWY_LOCATION", "AWY_DESIGNATION",
                    "AIRWAY_STRING",
                ],
                [
                    {
                        "AWY_ID": "V1", "AWY_LOCATION": "H",
                        "AWY_DESIGNATION": "HIGH",
                        "AIRWAY_STRING": "FIXA AA",
                    }
                ],
            )
            write_csv(
                raw / "AWY_SEG_ALT.csv",
                [
                    "AWY_ID", "AWY_LOCATION", "POINT_SEQ", "FROM_POINT",
                    "FROM_PT_TYPE", "TO_POINT", "MAG_COURSE_DIST",
                    "STATE_CODE", "COUNTRY_CODE", "ICAO_REGION_CODE",
                ],
                [
                    {
                        "AWY_ID": "V1", "AWY_LOCATION": "H",
                        "POINT_SEQ": "1", "FROM_POINT": "FIXA",
                        "FROM_PT_TYPE": "FIX", "TO_POINT": "WRONG",
                    },
                    {
                        "AWY_ID": "V1", "AWY_LOCATION": "H",
                        "POINT_SEQ": "2", "FROM_POINT": "AA",
                        "FROM_PT_TYPE": "NDB", "MAG_COURSE_DIST": "5",
                    },
                ],
            )
            write_csv(
                raw / "DP_BASE.csv",
                [
                    "DP_COMPUTER_CODE", "DP_NAME", "ARTCC", "SERVED_ARPT",
                    "AMENDMENT_NO",
                ],
                [
                    {
                        "DP_COMPUTER_CODE": "DP1.BODY", "DP_NAME": "Departure",
                        "ARTCC": "ZAA", "SERVED_ARPT": "AAA",
                    },
                    {
                        "DP_COMPUTER_CODE": "NOT ASSIGNED",
                        "DP_NAME": "Manual", "ARTCC": "ZAA",
                        "SERVED_ARPT": "AAA", "AMENDMENT_NO": "1",
                    },
                ],
            )
            write_csv(
                raw / "DP_RTE.csv",
                [
                    "DP_COMPUTER_CODE", "ROUTE_PORTION_TYPE", "ROUTE_NAME",
                    "BODY_SEQ", "TRANSITION_COMPUTER_CODE", "POINT_SEQ",
                    "POINT", "POINT_TYPE", "NEXT_POINT", "ARPT_RWY_ASSOC",
                    "DP_NAME", "ARTCC", "AMENDMENT_NO",
                ],
                [
                    {
                        "DP_COMPUTER_CODE": "DP1.BODY",
                        "ROUTE_PORTION_TYPE": "COMMON",
                        "ROUTE_NAME": "BODY", "BODY_SEQ": "1",
                        "TRANSITION_COMPUTER_CODE": "T1",
                        "POINT_SEQ": "1", "POINT": "FIXA",
                        "POINT_TYPE": "FIX", "NEXT_POINT": "WRONG",
                    },
                    {
                        "DP_COMPUTER_CODE": "DP1.BODY",
                        "ROUTE_PORTION_TYPE": "COMMON",
                        "ROUTE_NAME": "BODY", "BODY_SEQ": "1",
                        "TRANSITION_COMPUTER_CODE": "T1",
                        "POINT_SEQ": "2", "POINT": "AA",
                        "POINT_TYPE": "NDB",
                    },
                    {
                        "DP_COMPUTER_CODE": "NOT ASSIGNED",
                        "DP_NAME": "Manual", "ARTCC": "ZAA",
                        "AMENDMENT_NO": "1",
                        "ROUTE_PORTION_TYPE": "COMMON",
                        "ROUTE_NAME": "MANUAL", "BODY_SEQ": "1",
                        "TRANSITION_COMPUTER_CODE": "T1",
                        "POINT_SEQ": "1", "POINT": "AA",
                        "POINT_TYPE": "NDB",
                    },
                ],
            )
            write_csv(
                raw / "DP_APT.csv",
                [
                    "DP_COMPUTER_CODE", "BODY_NAME", "BODY_SEQ", "ARPT_ID",
                    "RWY_END_ID",
                ],
                [
                    {
                        "DP_COMPUTER_CODE": "DP1.BODY", "BODY_NAME": "BODY",
                        "BODY_SEQ": "1", "ARPT_ID": "AAA",
                        "RWY_END_ID": "09",
                    }
                ],
            )
            write_csv(
                raw / "STAR_BASE.csv",
                ["STAR_COMPUTER_CODE", "ARRIVAL_NAME", "ARTCC", "SERVED_ARPT"],
                [{"STAR_COMPUTER_CODE": "ST1", "ARRIVAL_NAME": "Arrival"}],
            )
            write_csv(
                raw / "STAR_RTE.csv",
                [
                    "STAR_COMPUTER_CODE", "ROUTE_PORTION_TYPE", "ROUTE_NAME",
                    "BODY_SEQ", "TRANSITION_COMPUTER_CODE", "POINT_SEQ",
                    "POINT", "POINT_TYPE", "NEXT_POINT", "ARPT_RWY_ASSOC",
                ],
                [],
            )
            write_csv(
                raw / "STAR_APT.csv",
                [
                    "STAR_COMPUTER_CODE", "BODY_NAME", "BODY_SEQ", "ARPT_ID",
                    "RWY_END_ID",
                ],
                [],
            )
            write_csv(
                raw / "PFR_BASE.csv",
                [
                    "ORIGIN_ID", "DSTN_ID", "PFR_TYPE_CODE", "ROUTE_NO",
                    "ROUTE_STRING",
                ],
                [
                    {
                        "ORIGIN_ID": "AAA", "DSTN_ID": "BBB",
                        "PFR_TYPE_CODE": "TEC", "ROUTE_NO": "1",
                        "ROUTE_STRING": "FIXA V1 DP1",
                    }
                ],
            )
            write_csv(
                raw / "PFR_SEG.csv",
                [
                    "ORIGIN_ID", "DSTN_ID", "PFR_TYPE_CODE", "ROUTE_NO",
                    "SEGMENT_SEQ", "SEG_VALUE", "SEG_TYPE", "NAV_TYPE",
                    "NEXT_SEG",
                ],
                [
                    {
                        "ORIGIN_ID": "AAA", "DSTN_ID": "BBB",
                        "PFR_TYPE_CODE": "TEC", "ROUTE_NO": "1",
                        "SEGMENT_SEQ": "1", "SEG_VALUE": "FIXA",
                        "SEG_TYPE": "FIX",
                    },
                    {
                        "ORIGIN_ID": "AAA", "DSTN_ID": "BBB",
                        "PFR_TYPE_CODE": "TEC", "ROUTE_NO": "1",
                        "SEGMENT_SEQ": "2", "SEG_VALUE": "V1",
                        "SEG_TYPE": "AIRWAY",
                    },
                    {
                        "ORIGIN_ID": "AAA", "DSTN_ID": "BBB",
                        "PFR_TYPE_CODE": "TEC", "ROUTE_NO": "1",
                        "SEGMENT_SEQ": "3", "SEG_VALUE": "DP1",
                        "SEG_TYPE": "DP",
                    },
                    {
                        "ORIGIN_ID": "AAA", "DSTN_ID": "BBB",
                        "PFR_TYPE_CODE": "TEC", "ROUTE_NO": "1",
                        "SEGMENT_SEQ": "4", "SEG_VALUE": "090",
                        "SEG_TYPE": "RADIAL",
                    },
                    {
                        "ORIGIN_ID": "AAA", "DSTN_ID": "BBB",
                        "PFR_TYPE_CODE": "TEC", "ROUTE_NO": "1",
                        "SEGMENT_SEQ": "5", "SEG_VALUE": "AA",
                        "SEG_TYPE": "NAVAID", "NAV_TYPE": "NDB",
                    },
                ],
            )
            write_csv(
                raw / "CDR.csv",
                [
                    "RCode", "Orig", "Dest", "DepFix", "Route String",
                    "DCNTR", "ACNTR", "TCNTRs", "CoordReq", "Play",
                    "NavEqp", "Length",
                ],
                [{"RCode": "R1", "Orig": "AAA", "Dest": "BBB"}],
            )

            report = build_clean_graph_data(raw, clean, audit)

            self.assertIn("clean_route_points.csv", {p.name for p in clean.glob("*.csv")})
            self.assertIn("audit_summary.csv", {p.name for p in audit.glob("*.csv")})

            route_points = read_csv(clean / "clean_route_points.csv")
            self.assertEqual(len(read_csv(clean / "rel_airport_has_runway.csv")), 1)
            self.assertEqual(len(read_csv(clean / "rel_runway_has_runway_end.csv")), 1)
            navaid_keys = [
                row["pointKey"] for row in route_points
                if row["pointType"] == "NAVAID"
            ]
            self.assertEqual(len(navaid_keys), 2)
            self.assertEqual(len(set(navaid_keys)), 2)

            airways = read_csv(clean / "clean_airways.csv")
            paths = read_csv(clean / "clean_airway_paths.csv")
            occurrences = read_csv(clean / "clean_airway_occurrences.csv")
            next_airway = read_csv(clean / "rel_next_on_airway.csv")
            self.assertEqual([row["airwayKey"] for row in airways], ["AIRWAY:V1"])
            self.assertEqual(
                [row["airwayPathKey"] for row in paths],
                ["AIRWAY_PATH:V1:H"],
            )
            self.assertEqual(
                [row["occurrenceRole"] for row in occurrences],
                ["START", "END"],
            )
            self.assertEqual(len(next_airway), 1)

            templates = read_csv(clean / "clean_route_templates.csv")
            tokens = read_csv(clean / "clean_template_tokens.csv")
            refs = read_csv(clean / "rel_template_token_references.csv")
            self.assertEqual(len(templates), 2)
            self.assertEqual(len(tokens), 5)
            self.assertEqual(
                {row["resolveStatus"] for row in tokens},
                {
                    "resolved_fix", "resolved_airway", "resolved_procedure",
                    "unsupported", "unresolved",
                },
            )
            self.assertEqual(len(refs), 3)

            procedure_paths = read_csv(clean / "clean_procedure_paths.csv")
            self.assertIn("sourceAggregation", procedure_paths[0])
            self.assertIn("sourceRowIds", procedure_paths[0])
            self.assertIn("sourceRowCount", procedure_paths[0])
            self.assertEqual(procedure_paths[0]["sourceAggregation"], "true")
            self.assertEqual(procedure_paths[0]["sourceRowCount"], "2")

            procedures = read_csv(clean / "clean_procedures.csv")
            self.assertIn(
                "PROCEDURE:DP:NOT_ASSIGNED:MANUAL:ZAA:1",
                {row["procedureKey"] for row in procedures},
            )
            runway_assoc = read_csv(
                clean / "rel_procedure_path_associated_with_runway_end.csv"
            )
            self.assertEqual(
                runway_assoc[0]["toKey"],
                "RWYEND:AAA:09/27:09",
            )

            duplicate_audit = read_csv(audit / "audit_duplicate_keys.csv")
            self.assertIn(
                ("APT_BASE", "AIRPORT:0.00E+00"),
                {(row["sourceTable"], row["key"]) for row in duplicate_audit},
            )
            self.assertIn(
                ("NAV_BASE", "POINT:NAVAID:AA:NDB"),
                {(row["sourceTable"], row["key"]) for row in duplicate_audit},
            )

            rejected = read_csv(audit / "audit_rejected_rows.csv")
            self.assertEqual(
                [row["reason"] for row in rejected],
                [
                    "invalid_or_duplicate_airport_key",
                    "invalid_or_duplicate_airport_key",
                ],
            )

            navaid_groups = read_csv(audit / "navaid_entity_group_analysis.csv")
            self.assertEqual(navaid_groups[0]["navId"], "AA")
            self.assertEqual(navaid_groups[0]["navType"], "NDB")
            self.assertEqual(navaid_groups[0]["groupSize"], "2")
            self.assertNotIn("should_merge", navaid_groups[0])
            self.assertNotIn("should_split", navaid_groups[0])

            navaid_detail = read_csv(audit / "navaid_entity_group_detail.csv")
            self.assertEqual(len(navaid_detail), 2)
            self.assertIn("currentPointKey", navaid_detail[0])

            navaid_refs = read_csv(
                audit / "navaid_reference_ambiguity_analysis.csv"
            )
            self.assertGreaterEqual(len(navaid_refs), 3)
            self.assertIn(
                "ambiguous_navaid_reference",
                {row["ambiguityReason"] for row in navaid_refs},
            )
            not_assigned_ref = next(
                row for row in navaid_refs
                if row["sourceTable"] == "DP_RTE"
                and "NOT_ASSIGNED" in row["sourceObjectKey"]
            )
            self.assertIn(
                "PROCEDURE:DP:NOT_ASSIGNED:MANUAL:ZAA:1",
                not_assigned_ref["sourceObjectKey"],
            )

            duplicate_review = read_csv(
                audit / "navaid_duplicate_groups_for_review.csv"
            )
            self.assertEqual(len(duplicate_review), 1)
            self.assertEqual(duplicate_review[0]["groupSize"], "2")
            self.assertEqual(duplicate_review[0]["nameConflict"], "true")
            self.assertEqual(
                duplicate_review[0]["referencedInAnyRouteData"], "true"
            )
            self.assertNotIn("should_merge", duplicate_review[0])
            self.assertNotIn("should_split", duplicate_review[0])

            ambiguous_review = read_csv(
                audit / "navaid_ambiguous_references_for_review.csv"
            )
            self.assertEqual(len(ambiguous_review), 4)
            self.assertTrue(
                all(
                    row["ambiguityReason"] == "ambiguous_navaid_reference"
                    for row in ambiguous_review
                )
            )

            sequence_issues = read_csv(audit / "audit_sequence_issues.csv")
            self.assertIn(
                "airway_to_next_from_mismatch",
                {row["issueType"] for row in sequence_issues},
            )
            self.assertIn(
                "procedure_next_point_mismatch",
                {row["issueType"] for row in sequence_issues},
            )

    def test_fails_fast_when_required_table_is_missing(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            raw = root / "raw"
            raw.mkdir()

            with self.assertRaisesRegex(ValueError, "Missing required NASR table"):
                build_clean_graph_data(raw, root / "clean", root / "audit")

    def test_fails_fast_when_required_column_is_missing(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            raw = root / "raw"
            raw.mkdir()
            for filename, columns in {
                "APT_BASE.csv": ["ARPT_NAME"],
                "APT_RWY.csv": ["ARPT_ID", "RWY_ID"],
                "APT_RWY_END.csv": ["ARPT_ID", "RWY_ID", "RWY_END_ID"],
                "FIX_BASE.csv": ["FIX_ID", "ICAO_REGION_CODE"],
                "NAV_BASE.csv": ["NAV_ID", "NAV_TYPE"],
                "AWY_BASE.csv": ["AWY_ID", "AWY_LOCATION"],
                "AWY_SEG_ALT.csv": [
                    "AWY_ID", "AWY_LOCATION", "POINT_SEQ", "FROM_POINT",
                    "FROM_PT_TYPE", "TO_POINT",
                ],
                "DP_BASE.csv": ["DP_COMPUTER_CODE"],
                "DP_RTE.csv": [
                    "DP_COMPUTER_CODE", "ROUTE_PORTION_TYPE", "ROUTE_NAME",
                    "BODY_SEQ", "TRANSITION_COMPUTER_CODE", "POINT_SEQ",
                    "POINT", "POINT_TYPE", "NEXT_POINT",
                ],
                "DP_APT.csv": [
                    "DP_COMPUTER_CODE", "BODY_NAME", "BODY_SEQ", "ARPT_ID",
                    "RWY_END_ID",
                ],
                "STAR_BASE.csv": ["STAR_COMPUTER_CODE"],
                "STAR_RTE.csv": [
                    "STAR_COMPUTER_CODE", "ROUTE_PORTION_TYPE", "ROUTE_NAME",
                    "BODY_SEQ", "TRANSITION_COMPUTER_CODE", "POINT_SEQ",
                    "POINT", "POINT_TYPE", "NEXT_POINT",
                ],
                "STAR_APT.csv": [
                    "STAR_COMPUTER_CODE", "BODY_NAME", "BODY_SEQ", "ARPT_ID",
                    "RWY_END_ID",
                ],
                "PFR_BASE.csv": [
                    "ORIGIN_ID", "DSTN_ID", "PFR_TYPE_CODE", "ROUTE_NO",
                ],
                "PFR_SEG.csv": [
                    "ORIGIN_ID", "DSTN_ID", "PFR_TYPE_CODE", "ROUTE_NO",
                    "SEGMENT_SEQ", "SEG_VALUE", "SEG_TYPE",
                ],
                "CDR.csv": ["RCode"],
            }.items():
                write_csv(raw / filename, columns, [])

            with self.assertRaisesRegex(
                ValueError, "Missing required column\\(s\\) in APT_BASE.csv: ARPT_ID"
            ):
                build_clean_graph_data(raw, root / "clean", root / "audit")


if __name__ == "__main__":
    unittest.main()
