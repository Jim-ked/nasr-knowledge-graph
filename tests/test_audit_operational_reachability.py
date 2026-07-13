import csv
import tempfile
import unittest
from pathlib import Path

from scripts.audit_operational_reachability import audit_operational_reachability


def write_csv(path, columns, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path):
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


AIRWAY_OCCURRENCE_COLUMNS = (
    "airwayOccurrenceKey", "airwayPathKey", "awyId", "awyLocation",
    "pointSeq", "rawFromPoint", "rawFromPointType", "rawToPoint",
    "rawNextMeaPoint", "resolvedPointKey", "resolveStatus",
    "occurrenceRole", "sourceCycle", "sourceTable", "sourceRowId",
)
AIRWAY_PATH_COLUMNS = (
    "airwayPathKey", "airwayKey", "awyId", "awyLocation",
    "awyDesignation", "airwayString", "sourceCycle", "sourceTable",
    "sourceRowId",
)
NEXT_AIRWAY_COLUMNS = (
    "fromKey", "toKey", "magCourse", "oppositeMagCourse", "distanceNm",
    "minEnrouteAltFt", "minEnrouteAltOppositeFt", "gpsMinEnrouteAltFt",
    "minObstacleClearanceAltFt", "minCrossingAltFt",
    "minReceptionAltFt", "maxAuthorizedAltFt", "requiredNavPerformance",
    "gapFlag", "signalGapFlag", "dogleg", "artcc", "stateCode",
    "countryCode", "icaoRegionCode", "sourceCycle", "sourceTable",
    "sourceRowId",
)
RESOLVE_COLUMNS = (
    "fromKey", "toKey", "rawValue", "normalizedValue", "resolveMethod",
    "resolveStatus", "confidence", "sourceCycle", "sourceTable",
    "sourceRowId",
)
PROCEDURE_PATH_COLUMNS = (
    "procedurePathKey", "procedureKey", "procedureType",
    "routePortionType", "routeName", "bodySeq", "transitionComputerCode",
    "sourceAggregation", "sourceRowIds", "sourceRowCount", "sourceCycle",
    "sourceTable", "sourceRowId",
)
PROCEDURE_OCCURRENCE_COLUMNS = (
    "procedureOccurrenceKey", "procedurePathKey", "procedureKey",
    "procedureType", "pointSeq", "rawPoint", "rawPointType",
    "nextPointRaw", "arptRwyAssoc", "resolvedPointKey", "resolveStatus",
    "sourceCycle", "sourceTable", "sourceRowId",
)
NEXT_PROCEDURE_COLUMNS = (
    "fromKey", "toKey", "sourceOrderNextPointRaw", "sequenceCheckStatus",
    "directionStatus", "sourceCycle", "sourceTable", "sourceRowId",
)
REL_COLUMNS = (
    "fromKey", "toKey", "sourceCycle", "sourceTable", "sourceRowId",
    "resolveStatus", "confidence",
)


def base_source(table, row_id):
    return {
        "sourceCycle": "2026-05-14",
        "sourceTable": table,
        "sourceRowId": str(row_id),
    }


class OperationalReachabilityAuditTests(unittest.TestCase):
    def make_clean_fixture(self, root):
        clean = root / "clean"
        output = root / "audit" / "reachability"
        clean.mkdir(parents=True)

        airway_occurrences = [
            self.airway_occ("A1", "AP1", "ENR1", "1"),
            self.airway_occ("A2", "AP1", "ENR2", "2"),
            self.airway_occ("A3", "AP1", "UNRES", "3"),
            self.airway_occ("A4", "AP1", "GAPPT", "4"),
        ]
        write_csv(clean / "clean_airway_occurrences.csv", AIRWAY_OCCURRENCE_COLUMNS, airway_occurrences)
        write_csv(
            clean / "clean_airway_paths.csv",
            AIRWAY_PATH_COLUMNS,
            [
                {
                    "airwayPathKey": "AP1",
                    "airwayKey": "AIRWAY:A1",
                    "awyId": "A1",
                    "awyLocation": "H",
                    "awyDesignation": "",
                    "airwayString": "",
                    **base_source("AWY_BASE", 1),
                }
            ],
        )
        write_csv(
            clean / "rel_next_on_airway.csv",
            NEXT_AIRWAY_COLUMNS,
            [
                self.next_airway("A1", "A2", "090", "270", "", ""),
                self.next_airway("A2", "A3", "", "", "", ""),
                self.next_airway("A1", "A4", "", "", "Y", ""),
            ],
        )
        write_csv(
            clean / "rel_airway_occurrence_resolves_to.csv",
            RESOLVE_COLUMNS,
            [
                self.resolve("A1", "POINT:ENR1"),
                self.resolve("A2", "POINT:ENR2"),
                self.resolve("A4", "POINT:GAPPT"),
            ],
        )

        paths = [
            self.proc_path("DP1_BODY", "PROC:DP1", "DP", "BODY", "DPSTART-JOIN"),
            self.proc_path("DP1_TRANS", "PROC:DP1", "DP", "TRANSITION", "JOIN-ENR1"),
            self.proc_path("STAR1_BODY", "PROC:STAR1", "STAR", "BODY", "JOIN2-RWY"),
            self.proc_path("STAR1_TRANS", "PROC:STAR1", "STAR", "TRANSITION", "ENR2-JOIN2"),
            self.proc_path("P2_BODY", "PROC:P2", "DP", "BODY", "X-J"),
            self.proc_path("P3_TRANS", "PROC:P3", "DP", "TRANSITION", "J-Y"),
            self.proc_path("PM_BODY1", "PROC:PM", "DP", "BODY", "B1-JM"),
            self.proc_path("PM_BODY2", "PROC:PM", "DP", "BODY", "B2-JM"),
            self.proc_path("PM_TRANS1", "PROC:PM", "DP", "TRANSITION", "JM-T1"),
            self.proc_path("PM_TRANS2", "PROC:PM", "DP", "TRANSITION", "JM-T2"),
            self.proc_path("UNRES_BODY", "PROC:UNRES", "DP", "BODY", "UA-UB"),
            self.proc_path("UNRES_TRANS", "PROC:UNRES", "DP", "TRANSITION", "UB-UC"),
        ]
        occurrences = []
        next_procedure = []
        resolves = []
        for path_key, proc_key, proc_type, points in [
            ("DP1_BODY", "PROC:DP1", "DP", [("DPSTART", "POINT:DPSTART"), ("JOIN", "POINT:JOIN")]),
            ("DP1_TRANS", "PROC:DP1", "DP", [("JOIN", "POINT:JOIN"), ("ENR1", "POINT:ENR1")]),
            ("STAR1_BODY", "PROC:STAR1", "STAR", [("JOIN2", "POINT:JOIN2"), ("RWY", "POINT:RWY")]),
            ("STAR1_TRANS", "PROC:STAR1", "STAR", [("ENR2", "POINT:ENR2"), ("JOIN2", "POINT:JOIN2")]),
            ("P2_BODY", "PROC:P2", "DP", [("X", "POINT:X"), ("J", "POINT:J")]),
            ("P3_TRANS", "PROC:P3", "DP", [("J", "POINT:J"), ("Y", "POINT:Y")]),
            ("PM_BODY1", "PROC:PM", "DP", [("B1", "POINT:B1"), ("JM", "POINT:JM")]),
            ("PM_BODY2", "PROC:PM", "DP", [("B2", "POINT:B2"), ("JM", "POINT:JM")]),
            ("PM_TRANS1", "PROC:PM", "DP", [("JM", "POINT:JM"), ("T1", "POINT:T1")]),
            ("PM_TRANS2", "PROC:PM", "DP", [("JM", "POINT:JM"), ("T2", "POINT:T2")]),
            ("UNRES_BODY", "PROC:UNRES", "DP", [("UA", ""), ("UB", "")]),
            ("UNRES_TRANS", "PROC:UNRES", "DP", [("UB", ""), ("UC", "")]),
        ]:
            keys = []
            for index, (raw, point_key) in enumerate(points, start=1):
                occ_key = f"{path_key}:O{index}"
                keys.append(occ_key)
                occurrences.append(self.proc_occ(occ_key, path_key, proc_key, proc_type, index, raw, point_key))
                if point_key:
                    resolves.append(self.resolve(occ_key, point_key))
            if len(keys) == 2:
                next_procedure.append(self.next_procedure(keys[0], keys[1], points[0][0]))

        write_csv(clean / "clean_procedure_paths.csv", PROCEDURE_PATH_COLUMNS, paths)
        write_csv(clean / "clean_procedure_occurrences.csv", PROCEDURE_OCCURRENCE_COLUMNS, occurrences)
        write_csv(clean / "rel_next_on_procedure.csv", NEXT_PROCEDURE_COLUMNS, next_procedure)
        write_csv(clean / "rel_procedure_occurrence_resolves_to.csv", RESOLVE_COLUMNS, resolves)
        write_csv(
            clean / "rel_procedure_serves_airport.csv",
            REL_COLUMNS,
            [
                {"fromKey": "PROC:DP1", "toKey": "AIRPORT:AAA", **base_source("DP_APT", 1), "resolveStatus": "resolved", "confidence": "high"}
            ],
        )
        write_csv(
            clean / "rel_procedure_path_associated_with_runway_end.csv",
            REL_COLUMNS,
            [
                {"fromKey": "DP1_BODY", "toKey": "RWYEND:AAA:01:01", **base_source("DP_APT", 2), "resolveStatus": "resolved", "confidence": "high"}
            ],
        )
        return clean, output

    def airway_occ(self, key, path, raw, seq):
        return {
            "airwayOccurrenceKey": key,
            "airwayPathKey": path,
            "awyId": "A1",
            "awyLocation": "H",
            "pointSeq": seq,
            "rawFromPoint": raw,
            "rawFromPointType": "FIX",
            "rawToPoint": "",
            "rawNextMeaPoint": "",
            "resolvedPointKey": "",
            "resolveStatus": "",
            "occurrenceRole": "",
            **base_source("AWY_SEG_ALT", seq),
        }

    def next_airway(self, from_key, to_key, mag, opposite, gap, signal_gap):
        return {
            "fromKey": from_key, "toKey": to_key, "magCourse": mag,
            "oppositeMagCourse": opposite, "distanceNm": "",
            "minEnrouteAltFt": "", "minEnrouteAltOppositeFt": opposite,
            "gpsMinEnrouteAltFt": "", "minObstacleClearanceAltFt": "",
            "minCrossingAltFt": "", "minReceptionAltFt": "",
            "maxAuthorizedAltFt": "", "requiredNavPerformance": "",
            "gapFlag": gap, "signalGapFlag": signal_gap, "dogleg": "",
            "artcc": "", "stateCode": "", "countryCode": "",
            "icaoRegionCode": "", **base_source("AWY_SEG_ALT", from_key),
        }

    def resolve(self, from_key, to_key):
        return {
            "fromKey": from_key, "toKey": to_key, "rawValue": "",
            "normalizedValue": "", "resolveMethod": "test",
            "resolveStatus": "resolved", "confidence": "high",
            **base_source("TEST", from_key),
        }

    def proc_path(self, key, proc, proc_type, portion, route_name):
        return {
            "procedurePathKey": key, "procedureKey": proc,
            "procedureType": proc_type, "routePortionType": portion,
            "routeName": route_name, "bodySeq": "1",
            "transitionComputerCode": "", "sourceAggregation": "true",
            "sourceRowIds": "1|2", "sourceRowCount": "2",
            **base_source("DP_RTE" if proc_type == "DP" else "STAR_RTE", key),
        }

    def proc_occ(self, key, path, proc, proc_type, seq, raw, point_key):
        return {
            "procedureOccurrenceKey": key, "procedurePathKey": path,
            "procedureKey": proc, "procedureType": proc_type,
            "pointSeq": str(seq * 10), "rawPoint": raw,
            "rawPointType": "FIX", "nextPointRaw": "",
            "arptRwyAssoc": "", "resolvedPointKey": point_key,
            "resolveStatus": "resolved" if point_key else "unresolved",
            **base_source("DP_RTE" if proc_type == "DP" else "STAR_RTE", key),
        }

    def next_procedure(self, from_key, to_key, raw_next):
        return {
            "fromKey": from_key, "toKey": to_key,
            "sourceOrderNextPointRaw": raw_next,
            "sequenceCheckStatus": "ordered_by_point_seq",
            "directionStatus": "reversed_source_sequence",
            **base_source("DP_RTE", from_key),
        }

    def test_reachability_audit_outputs_mechanical_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            clean, output = self.make_clean_fixture(Path(temp))

            audit_operational_reachability(clean, output)

            airway = read_csv(output / "airway_direction_evidence.csv")
            status_by_edge = {
                (row["fromOccurrenceKey"], row["toOccurrenceKey"]): row["reverseEvidenceStatus"]
                for row in airway
            }
            self.assertEqual(status_by_edge[("A1", "A2")], "explicit_opposite_fields_present")
            self.assertEqual(status_by_edge[("A2", "A3")], "endpoint_unresolved")
            self.assertEqual(status_by_edge[("A1", "A4")], "gap_or_signal_gap_present")

            endpoints = read_csv(output / "procedure_path_endpoints.csv")
            endpoint_by_path = {row["procedurePathKey"]: row for row in endpoints}
            self.assertEqual(endpoint_by_path["DP1_BODY"]["operationalStartRawPoint"], "DPSTART")
            self.assertEqual(endpoint_by_path["DP1_BODY"]["operationalEndRawPoint"], "JOIN")

            joins = read_csv(output / "procedure_join_candidates.csv")
            self.assertIn(
                ("PROC:DP1", "DP1_BODY", "DP1_TRANS", "POINT:JOIN", "matched"),
                {
                    (
                        row["procedureKey"], row["bodyPathKey"],
                        row["transitionPathKey"], row["joinPointKey"],
                        row["joinStatus"],
                    )
                    for row in joins
                },
            )
            self.assertIn(
                ("PROC:STAR1", "STAR1_BODY", "STAR1_TRANS", "POINT:JOIN2", "matched"),
                {
                    (
                        row["procedureKey"], row["bodyPathKey"],
                        row["transitionPathKey"], row["joinPointKey"],
                        row["joinStatus"],
                    )
                    for row in joins
                },
            )
            self.assertFalse(
                any(
                    row["bodyPathKey"] == "P2_BODY"
                    and row["transitionPathKey"] == "P3_TRANS"
                    for row in joins
                )
            )
            self.assertEqual(
                sum(
                    1 for row in joins
                    if row["procedureKey"] == "PROC:PM"
                    and row["joinStatus"] == "matched"
                ),
                4,
            )
            self.assertTrue(
                any(
                    row["procedureKey"] == "PROC:UNRES"
                    and row["joinStatus"] != "matched"
                    and not row["joinPointKey"]
                    for row in joins
                )
            )

            interfaces = read_csv(output / "procedure_enroute_interface.csv")
            interface_by_variant = {
                (row["procedureKey"], row["bodyPathKey"], row["transitionPathKey"]): row
                for row in interfaces
            }
            self.assertEqual(interface_by_variant[("PROC:DP1", "DP1_BODY", "DP1_TRANS")]["interfacePointKey"], "POINT:ENR1")
            self.assertEqual(interface_by_variant[("PROC:DP1", "DP1_BODY", "DP1_TRANS")]["interfaceStatus"], "connected_to_airway_network")
            self.assertEqual(interface_by_variant[("PROC:STAR1", "STAR1_BODY", "STAR1_TRANS")]["interfacePointKey"], "POINT:ENR2")
            self.assertEqual(interface_by_variant[("PROC:STAR1", "STAR1_BODY", "STAR1_TRANS")]["interfaceStatus"], "connected_to_airway_network")

            direction_names = read_csv(output / "procedure_direction_name_audit.csv")
            self.assertIn(
                ("DP1_BODY", "matches_operational_endpoints"),
                {
                    (row["procedurePathKey"], row["directionNameStatus"])
                    for row in direction_names
                },
            )

    def test_outputs_do_not_contain_forbidden_derived_edge_names(self):
        with tempfile.TemporaryDirectory() as temp:
            clean, output = self.make_clean_fixture(Path(temp))

            audit_operational_reachability(clean, output)

            forbidden = [
                "TRAVERSE" + "_TO",
                "AIRWAY" + "_TRAVERSE" + "_TO",
                "PROCEDURE" + "_TRAVERSE" + "_TO",
                "ROUTE" + "_EDGE",
                "USES" + "_POINT",
                "USES" + "_AIRWAY",
                "USES" + "_PROCEDURE",
            ]
            source = Path("scripts/audit_operational_reachability.py").read_text(encoding="utf-8")
            self.assertFalse(any(term in source for term in forbidden))
            for path in output.glob("*.csv"):
                text = path.read_text(encoding="utf-8")
                self.assertFalse(any(term in text for term in forbidden), path.name)


if __name__ == "__main__":
    unittest.main()
