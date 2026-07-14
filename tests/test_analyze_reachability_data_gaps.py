import csv
import tempfile
import unittest
from pathlib import Path

from scripts.analyze_reachability_data_gaps import (
    analyze_reachability_data_gaps,
    airway_reverse_summary,
    flag_active,
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


ENDPOINT_COLUMNS = (
    "procedureKey", "procedureType", "procedurePathKey", "routePortionType",
    "routeName", "bodySeq", "transitionComputerCode", "occurrenceCount",
    "operationalStartOccurrenceKey", "operationalStartRawPoint",
    "operationalStartPointKey", "operationalStartResolveStatus",
    "operationalEndOccurrenceKey", "operationalEndRawPoint",
    "operationalEndPointKey", "operationalEndResolveStatus",
    "servedAirportCount", "runwayEndAssociationCount", "sourceTable",
    "sourceRowIds",
)
JOIN_COLUMNS = (
    "procedureKey", "procedureType", "bodyPathKey", "transitionPathKey",
    "bodyStartPointKey", "bodyEndPointKey", "transitionStartPointKey",
    "transitionEndPointKey", "joinPointKey", "joinStatus",
)
DIRECTION_COLUMNS = (
    "procedureKey", "procedureType", "procedurePathKey", "routeName",
    "routeNameFirstToken", "routeNameLastToken",
    "operationalStartRawPoint", "operationalEndRawPoint",
    "directionNameStatus",
)
AIRWAY_COLUMNS = (
    "airwayKey", "airwayPathKey", "fromOccurrenceKey", "toOccurrenceKey",
    "fromPointKey", "toPointKey", "fromPointSeq", "toPointSeq",
    "magCourse", "oppositeMagCourse", "minEnrouteAltFt",
    "minEnrouteAltOppositeFt", "gpsMinEnrouteAltFt", "gapFlag",
    "signalGapFlag", "dogleg", "forwardEndpointResolved",
    "reverseDirectionEvidence", "reverseEvidenceStatus", "sourceTable",
    "sourceRowId",
)
VARIANT_COLUMNS = (
    "variantCandidateKey", "procedureKey", "procedureType", "bodyPathKey",
    "transitionPathKey", "operationalStartPointKey", "joinPointKey",
    "operationalEndPointKey", "servedAirportKeys",
    "associatedRunwayEndKeys", "variantStatus",
)
INTERFACE_COLUMNS = (
    "procedureKey", "procedureType", "bodyPathKey", "transitionPathKey",
    "interfacePointRole", "interfacePointKey", "interfaceRawPoint",
    "airwayOccurrenceCount", "airwayPathCount", "airwayCount",
    "interfaceStatus",
)


class ReachabilityDataGapAnalysisTests(unittest.TestCase):
    def make_fixture(self, root):
        clean = root / "clean"
        reachability = root / "reachability"
        output = root / "reachability_gaps"
        clean.mkdir()
        reachability.mkdir()

        endpoints = [
            self.endpoint("P_NORMAL", "DP", "P_NORMAL_BODY", "BODY", "A-B", "A", "POINT:A", "B", "POINT:B"),
            self.endpoint("P_UNRES", "DP", "P_UNRES_BODY", "BODY", "U-V", "U", "", "V", "POINT:V"),
            self.endpoint("P_DP", "DP", "DP_BODY", "BODY", "DB-DJ", "DB", "POINT:DB", "DJ", "POINT:DJ_BODY"),
            self.endpoint("P_DP", "DP", "DP_TRANS", "TRANSITION", "DJ-ENR", "DJ", "POINT:DJ_TRANS", "ENR", "POINT:ENR"),
            self.endpoint("P_STAR", "STAR", "STAR_BODY", "BODY", "SJ-RWY", "SJ", "POINT:SJ_BODY", "RWY", "POINT:RWY"),
            self.endpoint("P_STAR", "STAR", "STAR_TRANS", "TRANSITION", "ENR-SJ", "ENR", "POINT:ENR", "SJ", "POINT:SJ_TRANS"),
            self.endpoint("P_MULTI", "DP", "M_BODY1", "BODY", "M1-J", "M1", "POINT:M1", "J", "POINT:J"),
            self.endpoint("P_MULTI", "DP", "M_BODY2", "BODY", "M2-J", "M2", "POINT:M2", "J", "POINT:J"),
            self.endpoint("P_MULTI", "DP", "M_TRANS", "TRANSITION", "J-OUT", "J", "POINT:J", "OUT", "POINT:OUT"),
            self.endpoint("P_OTHER", "DP", "O_BODY", "BODY", "O-J", "O", "POINT:O", "J", "POINT:J"),
            self.endpoint("P_OTHER", "DP", "O_TRANS", "TRANSITION", "J-Z", "J", "POINT:J", "Z", "POINT:Z"),
            self.endpoint("P_FIRST", "DP", "FIRST", "BODY", "X-B", "A", "POINT:A", "B", "POINT:B"),
            self.endpoint("P_LAST", "DP", "LAST", "BODY", "A-X", "A", "POINT:A", "B", "POINT:B"),
            self.endpoint("P_BOTH", "DP", "BOTH", "BODY", "X-Y", "A", "POINT:A", "B", "POINT:B"),
        ]
        write_csv(reachability / "procedure_path_endpoints.csv", ENDPOINT_COLUMNS, endpoints)
        write_csv(
            reachability / "procedure_join_candidates.csv",
            JOIN_COLUMNS,
            [
                self.join("P_DP", "DP", "DP_BODY", "DP_TRANS", "POINT:DJ_BODY", "POINT:DJ_TRANS", "no_shared_join_point"),
                self.join("P_STAR", "STAR", "STAR_BODY", "STAR_TRANS", "POINT:SJ_BODY", "POINT:SJ_TRANS", "no_shared_join_point"),
                self.join("P_MULTI", "DP", "M_BODY1", "M_TRANS", "POINT:J", "POINT:J", "matched"),
                self.join("P_MULTI", "DP", "M_BODY2", "M_TRANS", "POINT:J", "POINT:J", "matched"),
                self.join("P_OTHER", "DP", "O_BODY", "O_TRANS", "POINT:J", "POINT:J", "matched"),
            ],
        )
        write_csv(
            reachability / "procedure_direction_name_audit.csv",
            DIRECTION_COLUMNS,
            [
                self.direction("P_FIRST", "DP", "FIRST", "X-B", "X", "B", "A", "B"),
                self.direction("P_LAST", "DP", "LAST", "A-X", "A", "X", "A", "B"),
                self.direction("P_BOTH", "DP", "BOTH", "X-Y", "X", "Y", "A", "B"),
            ],
        )
        write_csv(
            reachability / "airway_direction_evidence.csv",
            AIRWAY_COLUMNS,
            [
                self.airway("A1", "P1", "P2", "090", "12000", "", "", "N"),
                self.airway("A2", "P2", "P3", "090", "", "Y", "", "N"),
                self.airway("A3", "POINT:BOUNDARY:B1", "POINT:FIX:F1:K1", "", "", "Y", "", "Y"),
                self.airway("A4", "POINT:FIX:F2:K1", "POINT:BOUNDARY:B2", "", "", "", "NO", "FALSE"),
                self.airway("A5", "POINT:NAVAID:N1:VORTAC:US:AA:CITY", "POINT:NAVAID:N2:VORTAC:US:AA:CITY", "", "", "Y", "", "N"),
            ],
        )
        write_csv(
            reachability / "procedure_variant_candidates.csv",
            VARIANT_COLUMNS,
            [
                self.variant("P_MULTI", "DP", "M_BODY1", "M_TRANS", "POINT:OUT", "matched_body_transition"),
                self.variant("P_MULTI", "DP", "M_BODY2", "M_TRANS", "POINT:OUT", "matched_body_transition"),
                self.variant("P_OTHER", "DP", "O_BODY", "O_TRANS", "POINT:Z", "matched_body_transition"),
                self.variant("P_BODY_ONLY", "DP", "BODY_ONLY", "", "POINT:BO", "body_only_no_transition"),
                self.variant("P_TRANS_ONLY", "STAR", "", "TRANS_ONLY", "POINT:OUT", "transition_only_no_body"),
            ],
        )
        write_csv(
            reachability / "procedure_enroute_interface.csv",
            INTERFACE_COLUMNS,
            [
                self.interface("P_MULTI", "DP", "M_BODY1", "M_TRANS", "POINT:OUT", "connected_to_airway_network"),
                self.interface("P_MULTI", "DP", "M_BODY2", "M_TRANS", "POINT:OUT", "connected_to_airway_network"),
                self.interface("P_OTHER", "DP", "O_BODY", "O_TRANS", "POINT:OUT", "connected_to_airway_network"),
                self.interface("P_BODY_ONLY", "DP", "BODY_ONLY", "", "POINT:BO", "not_found_in_airway_network"),
                self.interface("P_TRANS_ONLY", "STAR", "", "TRANS_ONLY", "POINT:OUT", "connected_to_airway_network"),
            ],
        )
        return clean, reachability, output

    def endpoint(self, proc, proc_type, path, portion, route, start_raw, start_key, end_raw, end_key):
        return {
            "procedureKey": proc, "procedureType": proc_type,
            "procedurePathKey": path, "routePortionType": portion,
            "routeName": route, "bodySeq": "1",
            "transitionComputerCode": "", "occurrenceCount": "2",
            "operationalStartOccurrenceKey": f"{path}:S",
            "operationalStartRawPoint": start_raw,
            "operationalStartPointKey": start_key,
            "operationalStartResolveStatus": "resolved" if start_key else "unresolved",
            "operationalEndOccurrenceKey": f"{path}:E",
            "operationalEndRawPoint": end_raw,
            "operationalEndPointKey": end_key,
            "operationalEndResolveStatus": "resolved" if end_key else "unresolved",
            "servedAirportCount": "1", "runwayEndAssociationCount": "0",
            "sourceTable": "DP_RTE", "sourceRowIds": "1|2",
        }

    def join(self, proc, proc_type, body, trans, body_join, trans_join, status):
        return {
            "procedureKey": proc, "procedureType": proc_type,
            "bodyPathKey": body, "transitionPathKey": trans,
            "bodyStartPointKey": "", "bodyEndPointKey": body_join,
            "transitionStartPointKey": trans_join,
            "transitionEndPointKey": trans_join,
            "joinPointKey": body_join if status == "matched" else "",
            "joinStatus": status,
        }

    def direction(self, proc, proc_type, path, route, first, last, start, end):
        return {
            "procedureKey": proc, "procedureType": proc_type,
            "procedurePathKey": path, "routeName": route,
            "routeNameFirstToken": first, "routeNameLastToken": last,
            "operationalStartRawPoint": start, "operationalEndRawPoint": end,
            "directionNameStatus": "endpoint_name_mismatch",
        }

    def airway(self, airway, from_point, to_point, opposite_course, opposite_alt, gap, signal_gap, dogleg):
        return {
            "airwayKey": airway, "airwayPathKey": f"{airway}:PATH",
            "fromOccurrenceKey": f"{airway}:1", "toOccurrenceKey": f"{airway}:2",
            "fromPointKey": from_point, "toPointKey": to_point,
            "fromPointSeq": "1", "toPointSeq": "2",
            "magCourse": "270", "oppositeMagCourse": opposite_course,
            "minEnrouteAltFt": "10000", "minEnrouteAltOppositeFt": opposite_alt,
            "gpsMinEnrouteAltFt": "", "gapFlag": gap,
            "signalGapFlag": signal_gap, "dogleg": dogleg,
            "forwardEndpointResolved": "true", "reverseDirectionEvidence": "",
            "reverseEvidenceStatus": "", "sourceTable": "AWY_SEG_ALT",
            "sourceRowId": airway,
        }

    def variant(self, proc, proc_type, body, trans, end, status):
        return {
            "variantCandidateKey": f"{proc}|{body}|{trans}",
            "procedureKey": proc, "procedureType": proc_type,
            "bodyPathKey": body, "transitionPathKey": trans,
            "operationalStartPointKey": "", "joinPointKey": "",
            "operationalEndPointKey": end, "servedAirportKeys": "",
            "associatedRunwayEndKeys": "", "variantStatus": status,
        }

    def interface(self, proc, proc_type, body, trans, point, status):
        return {
            "procedureKey": proc, "procedureType": proc_type,
            "bodyPathKey": body, "transitionPathKey": trans,
            "interfacePointRole": "test", "interfacePointKey": point,
            "interfaceRawPoint": point.rsplit(":", 1)[-1],
            "airwayOccurrenceCount": "1" if status == "connected_to_airway_network" else "0",
            "airwayPathCount": "1" if status == "connected_to_airway_network" else "0",
            "airwayCount": "1" if status == "connected_to_airway_network" else "0",
            "interfaceStatus": status,
        }

    def test_gap_analysis_outputs_expected_details_and_summaries(self):
        with tempfile.TemporaryDirectory() as temp:
            clean, reachability, output = self.make_fixture(Path(temp))

            analyze_reachability_data_gaps(clean, reachability, output, validate_expected_counts=False)

            unresolved = read_csv(output / "procedure_endpoint_unresolved_detail.csv")
            self.assertEqual(len(unresolved), 1)
            self.assertEqual(unresolved[0]["endpointRole"], "operational_start")
            self.assertFalse(
                any(row["procedurePathKey"] == "P_NORMAL_BODY" for row in unresolved)
            )

            join = read_csv(output / "procedure_join_mismatch_detail.csv")
            join_by_proc = {row["procedureKey"]: row for row in join}
            self.assertEqual(join_by_proc["P_DP"]["bodyJoinRawPoint"], "DJ")
            self.assertEqual(join_by_proc["P_DP"]["transitionJoinRawPoint"], "DJ")
            self.assertEqual(join_by_proc["P_DP"]["pointKeysEqual"], "false")
            self.assertEqual(join_by_proc["P_STAR"]["bodyJoinRawPoint"], "SJ")
            self.assertEqual(join_by_proc["P_STAR"]["transitionJoinRawPoint"], "SJ")

            names = {
                row["procedurePathKey"]: row["possibleCause"]
                for row in read_csv(output / "procedure_direction_name_mismatch_detail.csv")
            }
            self.assertEqual(names["FIRST"], "first_token_mismatch")
            self.assertEqual(names["LAST"], "last_token_mismatch")
            self.assertEqual(names["BOTH"], "both_tokens_mismatch")

            airway = read_csv(output / "airway_reverse_evidence_detail.csv")
            classes = {row["airwayKey"]: row["reverseEvidenceClass"] for row in airway}
            self.assertEqual(classes["A1"], "opposite_fields_no_gap")
            self.assertEqual(classes["A2"], "opposite_fields_with_gap")
            self.assertEqual(classes["A3"], "no_opposite_fields_with_gap")
            self.assertEqual(classes["A4"], "no_opposite_fields_no_gap")
            self.assertEqual(classes["A5"], "no_opposite_fields_with_gap")
            inactive = {value: flag_active(value) for value in ["", "N", "NO", "0", "FALSE"]}
            self.assertTrue(all(value is False for value in inactive.values()))

            patterns = {
                (
                    row["fromPointKind"], row["toPointKind"],
                    row["anyGapActive"], row["doglegActive"],
                )
                for row in read_csv(output / "airway_no_opposite_endpoint_pattern.csv")
            }
            self.assertIn(("BOUNDARY_POINT", "FIX", "true", "true"), patterns)
            self.assertIn(("FIX", "BOUNDARY_POINT", "false", "false"), patterns)
            self.assertIn(("NAVAID", "NAVAID", "true", "false"), patterns)

            detail = read_csv(output / "procedure_interface_gap_detail.csv")
            complete = [row for row in detail if row["isCompleteMatchedVariant"] == "true"]
            self.assertEqual(len(complete), 3)
            self.assertFalse(
                any(
                    row["variantStatus"] in {"body_only_no_transition", "transition_only_no_body"}
                    and row["isCompleteMatchedVariant"] == "true"
                    for row in detail
                )
            )

            summary = read_csv(output / "procedure_interface_gap_summary.csv")
            rows_by_scope = {(row["scope"], row["procedureType"], row["variantStatus"], row["interfaceStatus"]): row for row in summary}
            self.assertEqual(
                rows_by_scope[("variant_row", "DP", "matched_body_transition", "connected_to_airway_network")]["rowCount"],
                "3",
            )
            self.assertEqual(
                rows_by_scope[("procedure_transition_point", "DP", "matched_body_transition", "connected_to_airway_network")]["rowCount"],
                "2",
            )
            self.assertEqual(
                rows_by_scope[("procedure_point", "DP", "matched_body_transition", "connected_to_airway_network")]["rowCount"],
                "2",
            )
            self.assertEqual(
                rows_by_scope[("category_distinct_point", "DP", "matched_body_transition", "connected_to_airway_network")]["rowCount"],
                "1",
            )

            unique_points = {
                row["interfacePointKey"]: row
                for row in read_csv(output / "unique_interface_points.csv")
            }
            self.assertEqual(unique_points["POINT:OUT"]["usedByDP"], "true")
            self.assertEqual(unique_points["POINT:OUT"]["usedBySTAR"], "true")
            self.assertIn("matched_body_transition", unique_points["POINT:OUT"]["variantStatuses"])
            self.assertIn("transition_only_no_body", unique_points["POINT:OUT"]["variantStatuses"])

            procedure_summary = read_csv(output / "procedure_interface_procedure_summary.csv")
            by_proc = {row["procedureKey"]: row for row in procedure_summary}
            self.assertEqual(by_proc["P_MULTI"]["matchedVariantCount"], "2")
            self.assertEqual(by_proc["P_MULTI"]["connectedMatchedVariantCount"], "2")
            self.assertEqual(by_proc["P_BODY_ONLY"]["onlyIncompleteVariants"], "true")

    def test_airway_reverse_summary_validates_internal_identities_only(self):
        rows = [
            {"oppositeFieldStatus": "both_present", "gapFlagActive": "false", "signalGapFlagActive": "false", "anyGapActive": "false", "doglegActive": "false", "reverseEvidenceClass": "opposite_fields_no_gap"},
            {"oppositeFieldStatus": "course_only", "gapFlagActive": "true", "signalGapFlagActive": "false", "anyGapActive": "true", "doglegActive": "false", "reverseEvidenceClass": "opposite_fields_with_gap"},
            {"oppositeFieldStatus": "opposite_alt_only", "gapFlagActive": "false", "signalGapFlagActive": "false", "anyGapActive": "false", "doglegActive": "false", "reverseEvidenceClass": "opposite_fields_no_gap"},
            {"oppositeFieldStatus": "none", "gapFlagActive": "false", "signalGapFlagActive": "true", "anyGapActive": "true", "doglegActive": "false", "reverseEvidenceClass": "no_opposite_fields_with_gap"},
            {"oppositeFieldStatus": "none", "gapFlagActive": "false", "signalGapFlagActive": "false", "anyGapActive": "false", "doglegActive": "false", "reverseEvidenceClass": "no_opposite_fields_no_gap"},
        ]
        summary = {
            row["metric"]: row["value"]
            for row in airway_reverse_summary(rows, validate_expected_counts=True)
        }
        self.assertEqual(summary["totalRows"], 5)
        self.assertEqual(summary["oppositeAnyFieldRows"], 3)

        broken = [dict(row) for row in rows]
        broken[-1]["reverseEvidenceClass"] = "opposite_fields_with_gap"
        with self.assertRaisesRegex(ValueError, "identity mismatch"):
            airway_reverse_summary(broken, validate_expected_counts=True)

    def test_format_or_suffix_difference_is_reachable(self):
        with tempfile.TemporaryDirectory() as temp:
            clean, reachability, output = self.make_fixture(Path(temp))
            direction_path = reachability / "procedure_direction_name_audit.csv"
            rows = read_csv(direction_path)
            rows.append(
                self.direction(
                    "P_FORMAT", "DP", "P_NORMAL_BODY", "A_SUFFIX-B",
                    "A_SUFFIX", "B", "A", "B",
                )
            )
            write_csv(direction_path, DIRECTION_COLUMNS, rows)

            analyze_reachability_data_gaps(clean, reachability, output, validate_expected_counts=False)

            details = {
                row["procedureKey"]: row["possibleCause"]
                for row in read_csv(output / "procedure_direction_name_mismatch_detail.csv")
            }
            self.assertEqual(details["P_FORMAT"], "format_or_suffix_difference")

    def test_outputs_and_source_do_not_contain_forbidden_edge_names(self):
        with tempfile.TemporaryDirectory() as temp:
            clean, reachability, output = self.make_fixture(Path(temp))

            analyze_reachability_data_gaps(clean, reachability, output, validate_expected_counts=False)

            forbidden = [
                "TRAVERSE" + "_TO",
                "AIRWAY" + "_TRAVERSE" + "_TO",
                "PROCEDURE" + "_TRAVERSE" + "_TO",
                "ROUTE" + "_EDGE",
                "USES" + "_POINT",
                "USES" + "_AIRWAY",
                "USES" + "_PROCEDURE",
            ]
            source = Path("scripts/analyze_reachability_data_gaps.py").read_text(encoding="utf-8")
            self.assertFalse(any(term in source for term in forbidden))
            for path in output.glob("*.csv"):
                text = path.read_text(encoding="utf-8")
                self.assertFalse(any(term in text for term in forbidden), path.name)


if __name__ == "__main__":
    unittest.main()
