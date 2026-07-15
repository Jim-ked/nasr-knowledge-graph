import csv
import tempfile
import unittest
from pathlib import Path

from scripts.audit_airway_source_semantics import audit_airway_source_semantics


BASE_COLUMNS = (
    "EFF_DATE", "REGULATORY", "AWY_DESIGNATION", "AWY_LOCATION",
    "AWY_ID", "UPDATE_DATE", "REMARK", "AIRWAY_STRING",
)
SEG_COLUMNS = (
    "EFF_DATE", "REGULATORY", "AWY_LOCATION", "AWY_ID", "POINT_SEQ",
    "FROM_POINT", "FROM_PT_TYPE", "NAV_NAME", "NAV_CITY", "ARTCC",
    "ICAO_REGION_CODE", "STATE_CODE", "COUNTRY_CODE", "TO_POINT",
    "MAG_COURSE", "OPP_MAG_COURSE", "MAG_COURSE_DIST", "CHGOVR_PT",
    "CHGOVR_PT_NAME", "CHGOVR_PT_DIST", "AWY_SEG_GAP_FLAG",
    "SIGNAL_GAP_FLAG", "DOGLEG", "NEXT_MEA_PT", "MIN_ENROUTE_ALT",
    "MIN_ENROUTE_ALT_DIR", "MIN_ENROUTE_ALT_OPPOSITE",
    "MIN_ENROUTE_ALT_OPPOSITE_DIR", "GPS_MIN_ENROUTE_ALT",
    "GPS_MIN_ENROUTE_ALT_DIR", "GPS_MIN_ENROUTE_ALT_OPPOSITE",
    "GPS_MEA_OPPOSITE_DIR", "DD_IRU_MEA", "DD_IRU_MEA_DIR",
    "DD_I_MEA_OPPOSITE", "DD_I_MEA_OPPOSITE_DIR", "MIN_OBSTN_CLNC_ALT",
    "MIN_CROSS_ALT", "MIN_CROSS_ALT_DIR", "MIN_CROSS_ALT_NAV_PT",
    "MIN_CROSS_ALT_OPPOSITE", "MIN_CROSS_ALT_OPPOSITE_DIR",
    "MIN_RECEP_ALT", "MAX_AUTH_ALT", "MEA_GAP",
    "REQD_NAV_PERFORMANCE", "REMARK",
)
OCC_COLUMNS = (
    "airwayOccurrenceKey", "airwayPathKey", "awyId", "awyLocation",
    "pointSeq", "rawFromPoint", "rawFromPointType", "rawToPoint",
    "rawNextMeaPoint", "resolvedPointKey", "resolveStatus",
    "occurrenceRole", "sourceCycle", "sourceTable", "sourceRowId",
)
NEXT_COLUMNS = (
    "fromKey", "toKey", "magCourse", "oppositeMagCourse", "distanceNm",
    "minEnrouteAltFt", "minEnrouteAltOppositeFt", "gpsMinEnrouteAltFt",
    "minObstacleClearanceAltFt", "minCrossingAltFt", "minReceptionAltFt",
    "maxAuthorizedAltFt", "requiredNavPerformance", "gapFlag",
    "signalGapFlag", "dogleg", "artcc", "stateCode", "countryCode",
    "icaoRegionCode", "sourceCycle", "sourceTable", "sourceRowId",
)


def write_csv(path, columns, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path):
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


class AirwaySourceSemanticsAuditTests(unittest.TestCase):
    def make_fixture(self, root, airway_string="A B C", second_to_point="C"):
        source = root / "source"
        clean = root / "clean"
        future = root / "future"
        output = root / "output"
        source.mkdir()
        clean.mkdir()
        future.mkdir()

        write_csv(source / "AWY_BASE.csv", BASE_COLUMNS, [
            self.base_row("V1", "C", airway_string),
        ])
        write_csv(source / "AWY_SEG_ALT.csv", SEG_COLUMNS, [
            self.seg_row("V1", "C", "10", "A", "B", gap="Y", signal="Y", course="010.00"),
            self.seg_row("V1", "C", "20", "B", second_to_point, mea_gap="U"),
            self.seg_row("V1", "C", "30", "C", "", dogleg="Y"),
        ])
        write_csv(clean / "clean_airway_occurrences.csv", OCC_COLUMNS, [
            self.occ_row("V1", "C", "10", "A"),
            self.occ_row("V1", "C", "20", "B"),
            self.occ_row("V1", "C", "30", "C"),
        ])
        write_csv(clean / "rel_next_on_airway.csv", NEXT_COLUMNS, [
            self.next_row("V1", "C", "10", "20"),
            self.next_row("V1", "C", "20", "30"),
        ])
        write_csv(future / "AWY_BASE.csv", BASE_COLUMNS, [
            self.base_row("V1", "C", airway_string),
        ])
        future_seg_columns = (
            "EFF_DATE", "REGULATORY", "AWY_LOCATION", "AWY_ID",
            "NEW_FIELD", "POINT_SEQ", *SEG_COLUMNS[5:],
        )
        write_csv(future / "AWY_SEG_ALT.csv", future_seg_columns, [
            {"NEW_FIELD": "X", **self.seg_row("V1", "C", "10", "A", "B")},
        ])
        return source, clean, future, output

    def base_row(self, awy_id, location, string):
        return {
            "EFF_DATE": "2026/05/14", "REGULATORY": "Y",
            "AWY_DESIGNATION": "V", "AWY_LOCATION": location,
            "AWY_ID": awy_id, "UPDATE_DATE": "2026/01/01",
            "REMARK": "", "AIRWAY_STRING": string,
        }

    def seg_row(
        self, awy_id, location, seq, point, to_point, gap="N",
        signal="N", dogleg="N", mea_gap="", course="",
    ):
        row = {column: "" for column in SEG_COLUMNS}
        row.update({
            "EFF_DATE": "2026/05/14", "REGULATORY": "Y",
            "AWY_LOCATION": location, "AWY_ID": awy_id,
            "POINT_SEQ": seq, "FROM_POINT": point, "FROM_PT_TYPE": "WP",
            "TO_POINT": to_point, "MAG_COURSE": course,
            "OPP_MAG_COURSE": "190.00" if course else "",
            "MAG_COURSE_DIST": "5.0" if to_point else "",
            "AWY_SEG_GAP_FLAG": gap, "SIGNAL_GAP_FLAG": signal,
            "DOGLEG": dogleg, "NEXT_MEA_PT": to_point,
            "MIN_ENROUTE_ALT": "05000" if to_point else "",
            "MIN_ENROUTE_ALT_OPPOSITE": "06000" if to_point else "",
            "MEA_GAP": mea_gap,
        })
        return row

    def occ_row(self, awy_id, location, seq, point):
        return {
            "airwayOccurrenceKey": f"AWY_OCC:{awy_id}:{location}:{seq}",
            "airwayPathKey": f"AIRWAY_PATH:{awy_id}:{location}",
            "awyId": awy_id, "awyLocation": location, "pointSeq": seq,
            "rawFromPoint": point, "rawFromPointType": "WP",
            "rawToPoint": "", "rawNextMeaPoint": "",
            "resolvedPointKey": f"POINT:FIX:{point}",
            "resolveStatus": "resolved_fix", "occurrenceRole": "",
            "sourceCycle": "2026-05-14", "sourceTable": "AWY_SEG_ALT",
            "sourceRowId": seq,
        }

    def next_row(self, awy_id, location, from_seq, to_seq):
        row = {column: "" for column in NEXT_COLUMNS}
        row.update({
            "fromKey": f"AWY_OCC:{awy_id}:{location}:{from_seq}",
            "toKey": f"AWY_OCC:{awy_id}:{location}:{to_seq}",
            "sourceTable": "AWY_SEG_ALT", "sourceRowId": from_seq,
        })
        return row

    def test_three_points_create_two_source_adjacent_segments_and_terminal(self):
        with tempfile.TemporaryDirectory() as temp:
            source, clean, future, output = self.make_fixture(Path(temp))

            audit_airway_source_semantics(source, clean, output, future)

            alignment = read_csv(output / "airway_point_segment_alignment.csv")
            self.assertEqual(len(alignment), 3)
            self.assertEqual(
                [row["nextSegMatchesNextRow"] for row in alignment],
                ["true", "true", ""],
            )
            self.assertEqual(alignment[-1]["isTerminalPoint"], "true")
            self.assertEqual(alignment[-1]["segmentAttributePresent"], "false")

            summary = {row["metric"]: row["value"] for row in read_csv(output / "airway_source_semantics_summary.csv")}
            self.assertEqual(summary["sourcePointRowCount"], "3")
            self.assertEqual(summary["sourceExpectedAdjacentEdgeCount"], "2")

    def test_airway_string_match_and_clean_coverage(self):
        with tempfile.TemporaryDirectory() as temp:
            source, clean, future, output = self.make_fixture(Path(temp))

            audit_airway_source_semantics(source, clean, output, future)

            string_rows = read_csv(output / "airway_string_alignment.csv")
            self.assertEqual(string_rows[0]["exactTokenMatch"], "true")
            coverage = read_csv(output / "clean_airway_source_coverage.csv")
            self.assertEqual(coverage[0]["pointCountMatches"], "true")
            self.assertEqual(coverage[0]["edgeCountMatches"], "true")
            self.assertEqual(coverage[0]["coverageStatus"], "gap_requires_policy")

    def test_mismatches_are_reported_without_auto_correction(self):
        with tempfile.TemporaryDirectory() as temp:
            source, clean, future, output = self.make_fixture(
                Path(temp), airway_string="A X C", second_to_point="Z"
            )

            audit_airway_source_semantics(source, clean, output, future)

            alignment = read_csv(output / "airway_point_segment_alignment.csv")
            self.assertEqual(alignment[1]["nextSegMatchesNextRow"], "false")
            string_rows = read_csv(output / "airway_string_alignment.csv")
            self.assertEqual(string_rows[0]["exactTokenMatch"], "false")
            self.assertEqual(string_rows[0]["firstMismatchIndex"], "1")

    def test_gap_signal_mea_and_dogleg_are_classified_separately(self):
        with tempfile.TemporaryDirectory() as temp:
            source, clean, future, output = self.make_fixture(Path(temp))

            audit_airway_source_semantics(source, clean, output, future)

            classes = {
                row["pointSeq"]: row["gapPositionClass"]
                for row in read_csv(output / "airway_gap_position_audit.csv")
            }
            self.assertEqual(classes["10"], "airway_and_signal_gap")
            self.assertEqual(classes["20"], "mea_unusable")
            self.assertEqual(classes["30"], "terminal_flag")
            self.assertNotEqual(classes["30"], "airway_discontinuity")

    def test_field_distribution_keeps_direction_code_values(self):
        with tempfile.TemporaryDirectory() as temp:
            source, clean, future, output = self.make_fixture(Path(temp))

            audit_airway_source_semantics(source, clean, output, future)

            distribution = read_csv(output / "airway_field_value_distribution.csv")
            fields = {row["fieldName"] for row in distribution}
            self.assertIn("MIN_ENROUTE_ALT_DIR", fields)
            self.assertIn("GPS_MEA_OPPOSITE_DIR", fields)

    def test_schema_compare_identifies_added_and_reordered_columns(self):
        with tempfile.TemporaryDirectory() as temp:
            source, clean, future, output = self.make_fixture(Path(temp))

            audit_airway_source_semantics(source, clean, output, future)

            changes = read_csv(output / "nasr_2026_09_schema_change.csv")
            change_types = {row["changeType"] for row in changes}
            self.assertIn("added", change_types)
            self.assertIn("reordered", change_types)

    def test_missing_file_or_column_raises_value_error(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            clean = root / "clean"
            output = root / "output"
            source.mkdir()
            clean.mkdir()
            write_csv(source / "AWY_BASE.csv", BASE_COLUMNS, [])

            with self.assertRaisesRegex(ValueError, "Missing required source file"):
                audit_airway_source_semantics(source, clean, output)

            write_csv(source / "AWY_SEG_ALT.csv", ("AWY_ID",), [{"AWY_ID": "V1"}])
            with self.assertRaisesRegex(ValueError, "Missing required columns"):
                audit_airway_source_semantics(source, clean, output)

    def test_outputs_and_source_do_not_contain_forbidden_derived_edge_names(self):
        with tempfile.TemporaryDirectory() as temp:
            source, clean, future, output = self.make_fixture(Path(temp))

            audit_airway_source_semantics(source, clean, output, future)

            terms = [
                "TRAVERSE" + "_TO",
                "AIRWAY" + "_TRAVERSE" + "_TO",
                "PROCEDURE" + "_TRAVERSE" + "_TO",
                "ROUTE" + "_EDGE",
                "USES" + "_POINT",
                "USES" + "_AIRWAY",
                "USES" + "_PROCEDURE",
            ]
            paths = [Path("scripts/audit_airway_source_semantics.py")]
            paths.extend(output.glob("*.csv"))
            for path in paths:
                text = path.read_text(encoding="utf-8")
                for term in terms:
                    self.assertNotIn(term, text)


if __name__ == "__main__":
    unittest.main()
