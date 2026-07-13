import argparse
import csv
import shutil
from collections import Counter, defaultdict
from pathlib import Path


AIRWAY_DIRECTION_COLUMNS = (
    "airwayKey", "airwayPathKey", "fromOccurrenceKey", "toOccurrenceKey",
    "fromPointKey", "toPointKey", "fromPointSeq", "toPointSeq",
    "magCourse", "oppositeMagCourse", "minEnrouteAltFt",
    "minEnrouteAltOppositeFt", "gpsMinEnrouteAltFt", "gapFlag",
    "signalGapFlag", "dogleg", "forwardEndpointResolved",
    "reverseDirectionEvidence", "reverseEvidenceStatus", "sourceTable",
    "sourceRowId",
)
PROCEDURE_ENDPOINT_COLUMNS = (
    "procedureKey", "procedureType", "procedurePathKey", "routePortionType",
    "routeName", "bodySeq", "transitionComputerCode", "occurrenceCount",
    "operationalStartOccurrenceKey", "operationalStartRawPoint",
    "operationalStartPointKey", "operationalStartResolveStatus",
    "operationalEndOccurrenceKey", "operationalEndRawPoint",
    "operationalEndPointKey", "operationalEndResolveStatus",
    "servedAirportCount", "runwayEndAssociationCount", "sourceTable",
    "sourceRowIds",
)
PROCEDURE_JOIN_COLUMNS = (
    "procedureKey", "procedureType", "bodyPathKey", "transitionPathKey",
    "bodyStartPointKey", "bodyEndPointKey", "transitionStartPointKey",
    "transitionEndPointKey", "joinPointKey", "joinStatus",
)
PROCEDURE_VARIANT_COLUMNS = (
    "variantCandidateKey", "procedureKey", "procedureType", "bodyPathKey",
    "transitionPathKey", "operationalStartPointKey", "joinPointKey",
    "operationalEndPointKey", "servedAirportKeys",
    "associatedRunwayEndKeys", "variantStatus",
)
PROCEDURE_INTERFACE_COLUMNS = (
    "procedureKey", "procedureType", "bodyPathKey", "transitionPathKey",
    "interfacePointRole", "interfacePointKey", "interfaceRawPoint",
    "airwayOccurrenceCount", "airwayPathCount", "airwayCount",
    "interfaceStatus",
)
PROCEDURE_DIRECTION_NAME_COLUMNS = (
    "procedureKey", "procedureType", "procedurePathKey", "routeName",
    "routeNameFirstToken", "routeNameLastToken",
    "operationalStartRawPoint", "operationalEndRawPoint",
    "directionNameStatus",
)
SUMMARY_COLUMNS = ("metric", "value")


REQUIRED = {
    "clean_airway_occurrences.csv": {
        "airwayOccurrenceKey", "airwayPathKey", "pointSeq", "rawFromPoint",
    },
    "clean_airway_paths.csv": {"airwayPathKey", "airwayKey"},
    "rel_next_on_airway.csv": {
        "fromKey", "toKey", "magCourse", "oppositeMagCourse",
        "minEnrouteAltFt", "minEnrouteAltOppositeFt",
        "gpsMinEnrouteAltFt", "gapFlag", "signalGapFlag", "dogleg",
        "sourceTable", "sourceRowId",
    },
    "rel_airway_occurrence_resolves_to.csv": {"fromKey", "toKey"},
    "clean_procedure_paths.csv": {
        "procedurePathKey", "procedureKey", "procedureType",
        "routePortionType", "routeName", "bodySeq",
        "transitionComputerCode", "sourceTable", "sourceRowIds",
    },
    "clean_procedure_occurrences.csv": {
        "procedureOccurrenceKey", "procedurePathKey", "procedureKey",
        "procedureType", "pointSeq", "rawPoint", "resolvedPointKey",
        "resolveStatus",
    },
    "rel_next_on_procedure.csv": {"fromKey", "toKey"},
    "rel_procedure_occurrence_resolves_to.csv": {"fromKey", "toKey"},
    "rel_procedure_serves_airport.csv": {"fromKey", "toKey"},
    "rel_procedure_path_associated_with_runway_end.csv": {"fromKey", "toKey"},
}


def key_part(value):
    return "_".join(str(value or "").strip().upper().replace("/", "_").split())


def read_csv(path, required_columns):
    if not path.exists():
        raise ValueError(f"Missing required clean CSV: {path}")
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = set(reader.fieldnames or [])
        missing = sorted(required_columns - fieldnames)
        if missing:
            raise ValueError(f"Missing required column(s) in {path.name}: {', '.join(missing)}")
        return list(reader)


def write_csv(path, columns, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def load_clean(clean_dir):
    clean_dir = Path(clean_dir)
    return {
        name: read_csv(clean_dir / name, columns)
        for name, columns in REQUIRED.items()
    }


def point_resolve_map(rows):
    result = {}
    for row in rows:
        result[row["fromKey"]] = row["toKey"]
    return result


def airway_direction_status(row, from_point, to_point):
    if not from_point or not to_point:
        return "endpoint_unresolved"
    if flag_present(row.get("gapFlag")) or flag_present(row.get("signalGapFlag")):
        return "gap_or_signal_gap_present"
    if row.get("oppositeMagCourse") or row.get("minEnrouteAltOppositeFt"):
        return "explicit_opposite_fields_present"
    return "no_opposite_fields"


def flag_present(value):
    return key_part(value) not in {"", "N", "NO", "0", "FALSE"}


def airway_direction_evidence(data):
    occurrences = {
        row["airwayOccurrenceKey"]: row
        for row in data["clean_airway_occurrences.csv"]
    }
    path_to_airway = {
        row["airwayPathKey"]: row["airwayKey"]
        for row in data["clean_airway_paths.csv"]
    }
    resolves = point_resolve_map(data["rel_airway_occurrence_resolves_to.csv"])
    rows = []
    for rel in data["rel_next_on_airway.csv"]:
        from_occ = occurrences.get(rel["fromKey"], {})
        to_occ = occurrences.get(rel["toKey"], {})
        from_point = resolves.get(rel["fromKey"], "")
        to_point = resolves.get(rel["toKey"], "")
        status = airway_direction_status(rel, from_point, to_point)
        evidence = []
        for field in ("oppositeMagCourse", "minEnrouteAltOppositeFt"):
            if rel.get(field):
                evidence.append(field)
        rows.append({
            "airwayKey": path_to_airway.get(from_occ.get("airwayPathKey", ""), ""),
            "airwayPathKey": from_occ.get("airwayPathKey", ""),
            "fromOccurrenceKey": rel["fromKey"],
            "toOccurrenceKey": rel["toKey"],
            "fromPointKey": from_point,
            "toPointKey": to_point,
            "fromPointSeq": from_occ.get("pointSeq", ""),
            "toPointSeq": to_occ.get("pointSeq", ""),
            "magCourse": rel.get("magCourse", ""),
            "oppositeMagCourse": rel.get("oppositeMagCourse", ""),
            "minEnrouteAltFt": rel.get("minEnrouteAltFt", ""),
            "minEnrouteAltOppositeFt": rel.get("minEnrouteAltOppositeFt", ""),
            "gpsMinEnrouteAltFt": rel.get("gpsMinEnrouteAltFt", ""),
            "gapFlag": rel.get("gapFlag", ""),
            "signalGapFlag": rel.get("signalGapFlag", ""),
            "dogleg": rel.get("dogleg", ""),
            "forwardEndpointResolved": "true" if from_point and to_point else "false",
            "reverseDirectionEvidence": "|".join(evidence),
            "reverseEvidenceStatus": status,
            "sourceTable": rel.get("sourceTable", ""),
            "sourceRowId": rel.get("sourceRowId", ""),
        })
    rows.sort(key=lambda row: (row["airwayPathKey"], row["fromPointSeq"], row["fromOccurrenceKey"], row["toOccurrenceKey"]))
    return rows


def airway_summary(evidence):
    total = len(evidence)
    return [
        {"metric": "next_on_airway_rows", "value": total},
        {"metric": "resolved_endpoint_rows", "value": sum(1 for row in evidence if row["forwardEndpointResolved"] == "true")},
        {"metric": "opposite_mag_course_rows", "value": sum(1 for row in evidence if row["oppositeMagCourse"])},
        {"metric": "opposite_min_enroute_alt_rows", "value": sum(1 for row in evidence if row["minEnrouteAltOppositeFt"])},
        {"metric": "no_opposite_field_rows", "value": sum(1 for row in evidence if not row["oppositeMagCourse"] and not row["minEnrouteAltOppositeFt"])},
        {"metric": "gap_flag_rows", "value": sum(1 for row in evidence if row["gapFlag"])},
        {"metric": "signal_gap_flag_rows", "value": sum(1 for row in evidence if row["signalGapFlag"])},
        {"metric": "dogleg_rows", "value": sum(1 for row in evidence if row["dogleg"])},
        {"metric": "unresolved_endpoint_rows", "value": sum(1 for row in evidence if row["forwardEndpointResolved"] == "false")},
    ]


def procedure_endpoint_data(data):
    paths = {row["procedurePathKey"]: row for row in data["clean_procedure_paths.csv"]}
    occurrences_by_path = defaultdict(list)
    occurrences = {}
    for row in data["clean_procedure_occurrences.csv"]:
        occurrences[row["procedureOccurrenceKey"]] = row
        occurrences_by_path[row["procedurePathKey"]].append(row)

    resolves = point_resolve_map(data["rel_procedure_occurrence_resolves_to.csv"])
    incoming = defaultdict(set)
    outgoing = defaultdict(set)
    for row in data["rel_next_on_procedure.csv"]:
        outgoing[row["fromKey"]].add(row["toKey"])
        incoming[row["toKey"]].add(row["fromKey"])

    served = defaultdict(set)
    for row in data["rel_procedure_serves_airport.csv"]:
        served[row["fromKey"]].add(row["toKey"])

    runway = defaultdict(set)
    for row in data["rel_procedure_path_associated_with_runway_end.csv"]:
        runway[row["fromKey"]].add(row["toKey"])

    endpoint_rows = []
    endpoint_by_path = {}
    for path_key in sorted(paths):
        path = paths[path_key]
        path_occ = sorted(
            occurrences_by_path.get(path_key, []),
            key=lambda row: (sequence_value(row.get("pointSeq")), row["procedureOccurrenceKey"]),
        )
        keys = {row["procedureOccurrenceKey"] for row in path_occ}
        starts = [row for row in path_occ if not incoming[row["procedureOccurrenceKey"]] & keys]
        ends = [row for row in path_occ if not outgoing[row["procedureOccurrenceKey"]] & keys]
        start = starts[0] if len(starts) == 1 else {}
        end = ends[0] if len(ends) == 1 else {}
        start_key = start.get("procedureOccurrenceKey", "")
        end_key = end.get("procedureOccurrenceKey", "")
        start_point = resolves.get(start_key, start.get("resolvedPointKey", ""))
        end_point = resolves.get(end_key, end.get("resolvedPointKey", ""))
        item = {
            "procedureKey": path["procedureKey"],
            "procedureType": path["procedureType"],
            "procedurePathKey": path_key,
            "routePortionType": path.get("routePortionType", ""),
            "routeName": path.get("routeName", ""),
            "bodySeq": path.get("bodySeq", ""),
            "transitionComputerCode": path.get("transitionComputerCode", ""),
            "occurrenceCount": len(path_occ),
            "operationalStartOccurrenceKey": start_key,
            "operationalStartRawPoint": start.get("rawPoint", ""),
            "operationalStartPointKey": start_point,
            "operationalStartResolveStatus": start.get("resolveStatus", ""),
            "operationalEndOccurrenceKey": end_key,
            "operationalEndRawPoint": end.get("rawPoint", ""),
            "operationalEndPointKey": end_point,
            "operationalEndResolveStatus": end.get("resolveStatus", ""),
            "servedAirportCount": len(served[path["procedureKey"]]),
            "runwayEndAssociationCount": len(runway[path_key]),
            "sourceTable": path.get("sourceTable", ""),
            "sourceRowIds": path.get("sourceRowIds", ""),
        }
        endpoint_rows.append(item)
        endpoint_by_path[path_key] = item
    return endpoint_rows, endpoint_by_path, served, runway


def sequence_value(value):
    try:
        return int(float(value or "0"))
    except ValueError:
        return 0


def procedure_join_candidates(endpoint_by_path):
    by_proc = defaultdict(lambda: {"BODY": [], "TRANSITION": []})
    for row in endpoint_by_path.values():
        portion = key_part(row["routePortionType"])
        if portion in ("BODY", "TRANSITION"):
            by_proc[row["procedureKey"]][portion].append(row)

    candidates = []
    for proc_key in sorted(by_proc):
        bodies = sorted(by_proc[proc_key]["BODY"], key=lambda row: row["procedurePathKey"])
        transitions = sorted(by_proc[proc_key]["TRANSITION"], key=lambda row: row["procedurePathKey"])
        for body in bodies:
            for transition in transitions:
                proc_type = body["procedureType"]
                if proc_type == "DP":
                    body_join = body["operationalEndPointKey"]
                    transition_join = transition["operationalStartPointKey"]
                else:
                    body_join = body["operationalStartPointKey"]
                    transition_join = transition["operationalEndPointKey"]
                if not body_join:
                    status = "body_endpoint_unresolved"
                    join_point = ""
                elif not transition_join:
                    status = "transition_endpoint_unresolved"
                    join_point = ""
                elif body_join == transition_join:
                    status = "matched"
                    join_point = body_join
                else:
                    status = "no_shared_join_point"
                    join_point = ""
                candidates.append({
                    "procedureKey": proc_key,
                    "procedureType": proc_type,
                    "bodyPathKey": body["procedurePathKey"],
                    "transitionPathKey": transition["procedurePathKey"],
                    "bodyStartPointKey": body["operationalStartPointKey"],
                    "bodyEndPointKey": body["operationalEndPointKey"],
                    "transitionStartPointKey": transition["operationalStartPointKey"],
                    "transitionEndPointKey": transition["operationalEndPointKey"],
                    "joinPointKey": join_point,
                    "joinStatus": status,
                })
    return candidates


def procedure_join_summary(candidates, endpoint_by_path):
    with_both = set()
    matched = set()
    all_with_body = defaultdict(set)
    all_with_trans = defaultdict(set)
    for endpoint in endpoint_by_path.values():
        portion = key_part(endpoint["routePortionType"])
        if portion == "BODY":
            all_with_body[endpoint["procedureKey"]].add(endpoint["procedurePathKey"])
        if portion == "TRANSITION":
            all_with_trans[endpoint["procedureKey"]].add(endpoint["procedurePathKey"])
    for proc in set(all_with_body) & set(all_with_trans):
        with_both.add(proc)
    for row in candidates:
        if row["joinStatus"] == "matched":
            matched.add(row["procedureKey"])
    return [
        {"metric": "procedures_with_body_and_transition", "value": len(with_both)},
        {"metric": "procedures_with_any_matched_join", "value": len(matched)},
        {"metric": "procedures_with_no_matched_join", "value": len(with_both - matched)},
        {"metric": "dp_matched_join_rows", "value": sum(1 for row in candidates if row["procedureType"] == "DP" and row["joinStatus"] == "matched")},
        {"metric": "star_matched_join_rows", "value": sum(1 for row in candidates if row["procedureType"] == "STAR" and row["joinStatus"] == "matched")},
        {"metric": "endpoint_unresolved_join_rows", "value": sum(1 for row in candidates if row["joinStatus"] in {"body_endpoint_unresolved", "transition_endpoint_unresolved"})},
    ]


def procedure_variants(endpoint_by_path, joins, served, runway):
    by_proc = defaultdict(lambda: {"BODY": [], "TRANSITION": []})
    for endpoint in endpoint_by_path.values():
        portion = key_part(endpoint["routePortionType"])
        if portion in ("BODY", "TRANSITION"):
            by_proc[endpoint["procedureKey"]][portion].append(endpoint)

    join_by_pair = {
        (row["bodyPathKey"], row["transitionPathKey"]): row
        for row in joins
    }
    rows = []
    for proc_key in sorted(by_proc):
        bodies = sorted(by_proc[proc_key]["BODY"], key=lambda row: row["procedurePathKey"])
        transitions = sorted(by_proc[proc_key]["TRANSITION"], key=lambda row: row["procedurePathKey"])
        if bodies and transitions:
            for body in bodies:
                for transition in transitions:
                    join = join_by_pair[(body["procedurePathKey"], transition["procedurePathKey"])]
                    if join["joinStatus"] == "matched":
                        status = "matched_body_transition"
                    elif join["joinStatus"] in {"body_endpoint_unresolved", "transition_endpoint_unresolved"}:
                        status = "endpoint_unresolved"
                    else:
                        continue
                    rows.append(variant_row(proc_key, body["procedureType"], body, transition, join["joinPointKey"], status, served, runway))
        elif bodies:
            for body in bodies:
                rows.append(variant_row(proc_key, body["procedureType"], body, {}, "", "body_only_no_transition", served, runway))
        elif transitions:
            for transition in transitions:
                rows.append(variant_row(proc_key, transition["procedureType"], {}, transition, "", "transition_only_no_body", served, runway))
    rows.sort(key=lambda row: row["variantCandidateKey"])
    return rows


def variant_row(proc_key, proc_type, body, transition, join_point, status, served, runway):
    body_key = body.get("procedurePathKey", "")
    transition_key = transition.get("procedurePathKey", "")
    if proc_type == "DP":
        start = body.get("operationalStartPointKey", "")
        end = transition.get("operationalEndPointKey", "") or body.get("operationalEndPointKey", "")
    else:
        start = transition.get("operationalStartPointKey", "") or body.get("operationalStartPointKey", "")
        end = body.get("operationalEndPointKey", "")
    runway_keys = set()
    if body_key:
        runway_keys |= runway[body_key]
    if transition_key:
        runway_keys |= runway[transition_key]
    return {
        "variantCandidateKey": f"{proc_key}|{body_key}|{transition_key}",
        "procedureKey": proc_key,
        "procedureType": proc_type,
        "bodyPathKey": body_key,
        "transitionPathKey": transition_key,
        "operationalStartPointKey": start,
        "joinPointKey": join_point,
        "operationalEndPointKey": end,
        "servedAirportKeys": "|".join(sorted(served[proc_key])),
        "associatedRunwayEndKeys": "|".join(sorted(runway_keys)),
        "variantStatus": status,
    }


def airway_point_index(data):
    path_to_airway = {
        row["airwayPathKey"]: row["airwayKey"]
        for row in data["clean_airway_paths.csv"]
    }
    occurrence_to_path = {
        row["airwayOccurrenceKey"]: row["airwayPathKey"]
        for row in data["clean_airway_occurrences.csv"]
    }
    result = defaultdict(lambda: {"occurrences": set(), "paths": set(), "airways": set()})
    for row in data["rel_airway_occurrence_resolves_to.csv"]:
        point = row["toKey"]
        path = occurrence_to_path.get(row["fromKey"], "")
        airway = path_to_airway.get(path, "")
        result[point]["occurrences"].add(row["fromKey"])
        if path:
            result[point]["paths"].add(path)
        if airway:
            result[point]["airways"].add(airway)
    return result


def procedure_interfaces(variants, endpoint_by_path, airway_index):
    rows = []
    for variant in variants:
        proc_type = variant["procedureType"]
        body = endpoint_by_path.get(variant["bodyPathKey"], {})
        transition = endpoint_by_path.get(variant["transitionPathKey"], {})
        if proc_type == "DP":
            if transition:
                role = "transition_operational_end"
                point = transition.get("operationalEndPointKey", "")
                raw = transition.get("operationalEndRawPoint", "")
                status = connected_status(point, airway_index)
            else:
                role = "body_operational_end"
                point = body.get("operationalEndPointKey", "")
                raw = body.get("operationalEndRawPoint", "")
                status = "endpoint_unresolved" if not point else "provisional_body_end"
        else:
            if transition:
                role = "transition_operational_start"
                point = transition.get("operationalStartPointKey", "")
                raw = transition.get("operationalStartRawPoint", "")
                status = connected_status(point, airway_index)
            else:
                role = "body_operational_start"
                point = body.get("operationalStartPointKey", "")
                raw = body.get("operationalStartRawPoint", "")
                status = "endpoint_unresolved" if not point else "provisional_body_start"
        index = airway_index.get(point, {"occurrences": set(), "paths": set(), "airways": set()})
        rows.append({
            "procedureKey": variant["procedureKey"],
            "procedureType": proc_type,
            "bodyPathKey": variant["bodyPathKey"],
            "transitionPathKey": variant["transitionPathKey"],
            "interfacePointRole": role,
            "interfacePointKey": point,
            "interfaceRawPoint": raw,
            "airwayOccurrenceCount": len(index["occurrences"]),
            "airwayPathCount": len(index["paths"]),
            "airwayCount": len(index["airways"]),
            "interfaceStatus": status,
        })
    rows.sort(key=lambda row: (row["procedureKey"], row["bodyPathKey"], row["transitionPathKey"]))
    return rows


def connected_status(point, airway_index):
    if not point:
        return "endpoint_unresolved"
    if airway_index.get(point, {}).get("occurrences"):
        return "connected_to_airway_network"
    return "not_found_in_airway_network"


def direction_name_audit(endpoint_by_path):
    rows = []
    for endpoint in sorted(endpoint_by_path.values(), key=lambda row: row["procedurePathKey"]):
        if key_part(endpoint["routePortionType"]) != "BODY":
            continue
        route_name = endpoint["routeName"]
        parts = [part.strip() for part in route_name.split("-")]
        if len(parts) != 2 or not parts[0] or not parts[1]:
            first = parts[0] if parts else ""
            last = parts[-1] if parts else ""
            status = "name_not_parseable"
        else:
            first, last = parts
            start = endpoint["operationalStartRawPoint"]
            end = endpoint["operationalEndRawPoint"]
            if not endpoint["operationalStartPointKey"] or not endpoint["operationalEndPointKey"]:
                status = "endpoint_unresolved"
            elif key_part(first) == key_part(start) and key_part(last) == key_part(end):
                status = "matches_operational_endpoints"
            elif key_part(first) == key_part(end) and key_part(last) == key_part(start):
                status = "reversed_against_operational_endpoints"
            else:
                status = "endpoint_name_mismatch"
        rows.append({
            "procedureKey": endpoint["procedureKey"],
            "procedureType": endpoint["procedureType"],
            "procedurePathKey": endpoint["procedurePathKey"],
            "routeName": route_name,
            "routeNameFirstToken": first,
            "routeNameLastToken": last,
            "operationalStartRawPoint": endpoint["operationalStartRawPoint"],
            "operationalEndRawPoint": endpoint["operationalEndRawPoint"],
            "directionNameStatus": status,
        })
    return rows


def total_summary(airway_evidence, endpoints, joins, variants, interfaces, direction_names):
    endpoint_unresolved = sum(
        1 for row in endpoints
        if not row["operationalStartPointKey"] or not row["operationalEndPointKey"]
    )
    return [
        {"metric": "airway_edge_candidate_rows", "value": len(airway_evidence)},
        {"metric": "airway_resolved_endpoint_rows", "value": sum(1 for row in airway_evidence if row["forwardEndpointResolved"] == "true")},
        {"metric": "airway_explicit_opposite_field_rows", "value": sum(1 for row in airway_evidence if row["reverseEvidenceStatus"] == "explicit_opposite_fields_present")},
        {"metric": "airway_no_opposite_field_rows", "value": sum(1 for row in airway_evidence if row["reverseEvidenceStatus"] == "no_opposite_fields")},
        {"metric": "procedure_path_rows", "value": len(endpoints)},
        {"metric": "procedure_path_endpoint_unresolved_rows", "value": endpoint_unresolved},
        {"metric": "procedure_join_candidate_rows", "value": len(joins)},
        {"metric": "procedure_join_matched_rows", "value": sum(1 for row in joins if row["joinStatus"] == "matched")},
        {"metric": "procedure_variant_candidate_rows", "value": len(variants)},
        {"metric": "dp_interface_connected_rows", "value": sum(1 for row in interfaces if row["procedureType"] == "DP" and row["interfaceStatus"] == "connected_to_airway_network")},
        {"metric": "dp_interface_not_connected_rows", "value": sum(1 for row in interfaces if row["procedureType"] == "DP" and row["interfaceStatus"] == "not_found_in_airway_network")},
        {"metric": "star_interface_connected_rows", "value": sum(1 for row in interfaces if row["procedureType"] == "STAR" and row["interfaceStatus"] == "connected_to_airway_network")},
        {"metric": "star_interface_not_connected_rows", "value": sum(1 for row in interfaces if row["procedureType"] == "STAR" and row["interfaceStatus"] == "not_found_in_airway_network")},
        {"metric": "procedure_direction_name_match_rows", "value": sum(1 for row in direction_names if row["directionNameStatus"] == "matches_operational_endpoints")},
        {"metric": "procedure_direction_name_reversed_rows", "value": sum(1 for row in direction_names if row["directionNameStatus"] == "reversed_against_operational_endpoints")},
        {"metric": "procedure_direction_name_mismatch_rows", "value": sum(1 for row in direction_names if row["directionNameStatus"] == "endpoint_name_mismatch")},
    ]


def reset_output_dir(output_dir):
    output_dir = Path(output_dir)
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)


def audit_operational_reachability(clean_dir, output_dir):
    data = load_clean(clean_dir)
    output_dir = Path(output_dir)
    reset_output_dir(output_dir)

    airway_evidence = airway_direction_evidence(data)
    endpoints, endpoint_by_path, served, runway = procedure_endpoint_data(data)
    joins = procedure_join_candidates(endpoint_by_path)
    variants = procedure_variants(endpoint_by_path, joins, served, runway)
    interfaces = procedure_interfaces(variants, endpoint_by_path, airway_point_index(data))
    direction_names = direction_name_audit(endpoint_by_path)

    write_csv(output_dir / "airway_direction_evidence.csv", AIRWAY_DIRECTION_COLUMNS, airway_evidence)
    write_csv(output_dir / "airway_direction_summary.csv", SUMMARY_COLUMNS, airway_summary(airway_evidence))
    write_csv(output_dir / "procedure_path_endpoints.csv", PROCEDURE_ENDPOINT_COLUMNS, endpoints)
    write_csv(output_dir / "procedure_join_candidates.csv", PROCEDURE_JOIN_COLUMNS, joins)
    write_csv(output_dir / "procedure_join_summary.csv", SUMMARY_COLUMNS, procedure_join_summary(joins, endpoint_by_path))
    write_csv(output_dir / "procedure_variant_candidates.csv", PROCEDURE_VARIANT_COLUMNS, variants)
    write_csv(output_dir / "procedure_enroute_interface.csv", PROCEDURE_INTERFACE_COLUMNS, interfaces)
    write_csv(output_dir / "procedure_direction_name_audit.csv", PROCEDURE_DIRECTION_NAME_COLUMNS, direction_names)
    write_csv(output_dir / "reachability_audit_summary.csv", SUMMARY_COLUMNS, total_summary(airway_evidence, endpoints, joins, variants, interfaces, direction_names))

    return {
        "airway_edge_candidate_rows": len(airway_evidence),
        "procedure_path_rows": len(endpoints),
        "procedure_join_candidate_rows": len(joins),
        "procedure_variant_candidate_rows": len(variants),
    }


def parse_args():
    parser = argparse.ArgumentParser(description="Audit inputs for operational reachability derivation.")
    parser.add_argument("--clean-dir", default=Path("data/clean"), type=Path)
    parser.add_argument("--output-dir", default=Path("data/audit/reachability"), type=Path)
    return parser.parse_args()


def main():
    args = parse_args()
    summary = audit_operational_reachability(args.clean_dir, args.output_dir)
    for key in sorted(summary):
        print(f"{key}: {summary[key]}")


if __name__ == "__main__":
    main()
