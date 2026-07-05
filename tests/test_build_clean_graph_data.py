import csv
import json
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from scripts.build_clean_graph_data import build_clean_graph_data, read_table


def write_csv(path, columns, rows):
    with path.open("w", encoding="cp1252", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


class CleanGraphDataTests(unittest.TestCase):
    def test_builds_three_node_types_and_deduplicated_bidirectional_edges(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            raw = root / "raw"
            clean = root / "clean"
            raw.mkdir()

            write_csv(
                raw / "APT_BASE.csv",
                ["ARPT_ID", "ARPT_NAME"],
                [
                    {"ARPT_ID": " aaa ", "ARPT_NAME": "Alpha"},
                    {"ARPT_ID": "BBB", "ARPT_NAME": "Beta"},
                ],
            )
            write_csv(
                raw / "PFR_BASE.csv",
                [
                    "ORIGIN_ID", "DSTN_ID", "PFR_TYPE_CODE", "ROUTE_NO",
                    "ROUTE_STRING",
                ],
                [
                    {
                        "ORIGIN_ID": "aaa", "DSTN_ID": "bbb",
                        "PFR_TYPE_CODE": "tec", "ROUTE_NO": "1",
                        "ROUTE_STRING": "ONE V1 TWO",
                    },
                    {
                        "ORIGIN_ID": "AAA", "DSTN_ID": "BBB",
                        "PFR_TYPE_CODE": "TEC", "ROUTE_NO": "2",
                    },
                    {
                        "ORIGIN_ID": "AAA", "DSTN_ID": "BBB",
                        "PFR_TYPE_CODE": "TEC", "ROUTE_NO": "3",
                    },
                ],
            )
            write_csv(
                raw / "PFR_SEG.csv",
                [
                    "ORIGIN_ID", "DSTN_ID", "PFR_TYPE_CODE", "ROUTE_NO",
                    "SEGMENT_SEQ", "SEG_VALUE", "SEG_TYPE", "NAV_TYPE",
                ],
                [
                    {
                        "ORIGIN_ID": "AAA", "DSTN_ID": "BBB",
                        "PFR_TYPE_CODE": "TEC", "ROUTE_NO": "1",
                        "SEGMENT_SEQ": "5", "SEG_VALUE": "ONE",
                        "SEG_TYPE": "FIX",
                    },
                    {
                        "ORIGIN_ID": "AAA", "DSTN_ID": "BBB",
                        "PFR_TYPE_CODE": "TEC", "ROUTE_NO": "1",
                        "SEGMENT_SEQ": "10", "SEG_VALUE": "V1",
                        "SEG_TYPE": "AIRWAY",
                    },
                    {
                        "ORIGIN_ID": "AAA", "DSTN_ID": "BBB",
                        "PFR_TYPE_CODE": "TEC", "ROUTE_NO": "1",
                        "SEGMENT_SEQ": "15", "SEG_VALUE": "TWO",
                        "SEG_TYPE": "NAVAID", "NAV_TYPE": "VOR",
                    },
                    {
                        "ORIGIN_ID": "AAA", "DSTN_ID": "BBB",
                        "PFR_TYPE_CODE": "TEC", "ROUTE_NO": "2",
                        "SEGMENT_SEQ": "5", "SEG_VALUE": "V2",
                        "SEG_TYPE": "AIRWAY",
                    },
                    {
                        "ORIGIN_ID": "AAA", "DSTN_ID": "BBB",
                        "PFR_TYPE_CODE": "TEC", "ROUTE_NO": "3",
                        "SEGMENT_SEQ": "5", "SEG_VALUE": "MISSING_FIX",
                        "SEG_TYPE": "FIX",
                    },
                    {
                        "ORIGIN_ID": "AAA", "DSTN_ID": "BBB",
                        "PFR_TYPE_CODE": "TEC", "ROUTE_NO": "3",
                        "SEGMENT_SEQ": "10", "SEG_VALUE": "MISSING_NAV",
                        "SEG_TYPE": "NAVAID", "NAV_TYPE": "VOR",
                    },
                ],
            )
            write_csv(
                raw / "FIX_BASE.csv",
                ["FIX_ID", "LAT_DECIMAL", "LONG_DECIMAL"],
                [{"FIX_ID": "ONE", "LAT_DECIMAL": "1", "LONG_DECIMAL": "2"}],
            )
            write_csv(
                raw / "NAV_BASE.csv",
                ["NAV_ID", "NAV_TYPE", "NAME"],
                [{"NAV_ID": "TWO", "NAV_TYPE": "VOR", "NAME": "Two"}],
            )

            report = build_clean_graph_data(raw, clean)

            self.assertEqual(report["valid_routes_before_point_filter"], 3)
            self.assertEqual(report["valid_routes_after_point_filter"], 1)
            self.assertEqual(report["airport_nodes"], 2)
            self.assertEqual(report["fix_nodes"], 1)
            self.assertEqual(report["navaid_nodes"], 1)
            self.assertEqual(report["original_edges"], 3)
            self.assertEqual(report["bidirectional_edges"], 6)
            self.assertEqual(report["dropped_non_point_segments"], 2)
            self.assertEqual(report["unmatched_fix_points"], 1)
            self.assertEqual(report["unmatched_navaid_points"], 1)

            with (clean / "rejected_routes.csv").open(
                encoding="utf-8", newline=""
            ) as handle:
                rejected = list(csv.DictReader(handle))
            self.assertEqual(
                [row["rejectReason"] for row in rejected],
                [
                    "no_fix_or_navaid_after_cleaning",
                    "no_fix_or_navaid_after_cleaning",
                ],
            )

            saved_report = json.loads(
                (clean / "cleaning_report.json").read_text(encoding="utf-8")
            )
            self.assertEqual(saved_report, report)

    def test_reads_a_table_from_a_nested_zip_folder(self):
        with tempfile.TemporaryDirectory() as temp:
            archive_path = Path(temp) / "nasr.zip"
            content = " arpt_id ,ARPT_NAME\r\n atl ,Atlanta\r\n"
            with ZipFile(archive_path, "w") as archive:
                archive.writestr(
                    "14_May_2026_CSV/APT_BASE.csv",
                    content.encode("cp1252"),
                )

            rows = read_table(archive_path, "APT_BASE.csv")

            self.assertEqual(rows, [{"ARPT_ID": "ATL", "ARPT_NAME": "Atlanta"}])


if __name__ == "__main__":
    unittest.main()
