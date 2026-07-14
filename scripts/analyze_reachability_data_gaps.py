import argparse
import csv
import shutil
from collections import defaultdict
from pathlib import Path


SUMMARY_COLUMNS = ("metric", "value")

UNRESOLVED_ENDPOINT_COLUMNS = (
    "procedureKey", "procedureType", "procedurePathKey", "routePortionType",
    "routeName", "endpointRole", "endpointOccurrenceKey",
    "endpointRawPoint", "endpointPointKey", "endpointResolveStatus",
    "occurrenceCount", "servedAirportCount", "runwayEndAssociationCount",
    "sourceTable", "sourceRowIds",
)
JOIN_MISMATCH_COLUMNS = (
    "procedureKey", "procedureType", "bodyPathKey", "transitionPathKey",
    "bodyRouteName", "transitionRouteName", "bodyStartRawPoint",
    "bodyEndRawPoint", "transitionStartRawPoint", "transitionEndRawPoint",
    "bodyJoinPointKey", "transitionJoinPointKey", "bodyJoinRawPoint",
    "transitionJoinRawPoint", "normalizedBodyJoinRawPoint",
    "normalizedTransitionJoinRawPoint", "rawPointNamesEqual",
    "pointKeysEqual", "sourceTables", "sourceRowIds",
)
DIRECTION_MISMATCH_COLUMNS = (
    "procedureKey", "procedureType", "procedurePathKey", "routeName",
    "routeNameFirstToken", "routeNameLastToken",
    "operationalStartRawPoint", "operationalEndRawPoint",
    "normalizedFirstToken", "normalizedLastToken",
    "normalizedStartRawPoint", "normalizedEndRawPoint",
    "startMatches", "endMatches", "possibleCause", "sourceTable",
    "sourceRowIds",
)
AIRWAY_REVERSE_COLUMNS = (
    "airwayKey", "airwayPathKey", "fromOccurrenceKey", "toOccurrenceKey",
    "fromPointKey", "toPointKey", "fromPointSeq", "toPointSeq",
    "magCourse", "oppositeMagCourse", "minEnrouteAltFt",
    "minEnrouteAltOppositeFt", "oppositeFieldStatus", "gapFlagRaw",
    "gapFlagActive", "signalGapFlagRaw", "signalGapFlagActive",
    "doglegRaw", "doglegActive", "anyGapActive",
    "reverseEvidenceClass", "sourceTable", "sourceRowId",
)
AIRWAY_NO_OPPOSITE_GROUP_COLUMNS = (
    "airwayKey", "airwayPathKey", "anyGapActive", "gapFlagRaw",
    "signalGapFlagRaw", "doglegRaw", "sourceTable", "rowCount",
    "sampleFromPointKeys", "sampleToPointKeys", "sampleSourceRowIds",
)
AIRWAY_NO_OPPOSITE_ENDPOINT_PATTERN_COLUMNS = (
    "fromPointKind", "toPointKind", "containsBoundaryPoint", "anyGapActive",
    "doglegActive", "airwayPrefix", "awyLocation", "rowCount",
    "airwayCount", "airwayPathCount", "sampleAirwayKeys",
    "sampleFromPointKeys", "sampleToPointKeys", "sampleSourceRowIds",
)
INTERFACE_DETAIL_COLUMNS = (
    "variantCandidateKey", "variantStatus", "procedureKey",
    "procedureType", "bodyPathKey", "transitionPathKey",
    "interfacePointRole", "interfacePointKey", "interfaceRawPoint",
    "pointKind", "airwayOccurrenceCount", "airwayPathCount",
    "airwayCount", "interfaceStatus", "isCompleteMatchedVariant",
    "dedupeProcedureTransitionPointKey", "dedupeProcedurePointKey",
)
INTERFACE_SUMMARY_COLUMNS = (
    "scope", "procedureType", "variantStatus", "pointKind",
    "interfaceStatus", "rowCount",
)
PROCEDURE_INTERFACE_SUMMARY_COLUMNS = (
    "procedureKey", "procedureType", "variantCount", "matchedVariantCount",
    "connectedMatchedVariantCount", "notConnectedMatchedVariantCount",
    "uniqueInterfacePointCount", "connectedInterfacePointCount",
    "hasAnyMatchedVariant", "hasAnyConnectedMatchedVariant",
    "allMatchedVariantsUnconnected", "onlyIncompleteVariants",
)
UNIQUE_INTERFACE_POINT_COLUMNS = (
    "interfacePointKey", "interfaceRawPoints", "pointKind", "usedByDP",
    "usedBySTAR", "procedureCount", "matchedProcedureCount",
    "matchedVariantCount", "incompleteVariantCount",
    "connectedToAirwayNetwork", "airwayOccurrenceCount",
    "airwayPathCount", "airwayCount", "procedureKeys",
    "variantStatuses",
)


REACHABILITY_REQUIRED = {
    "procedure_path_endpoints.csv": {
        "procedureKey", "procedureType", "procedurePathKey",
        "routePortionType", "routeName", "operationalStartOccurrenceKey",
        "operationalStartRawPoint", "operationalStartPointKey",
        "operationalStartResolveStatus", "operationalEndOccurrenceKey",
        "operationalEndRawPoint", "operationalEndPointKey",
        "operationalEndResolveStatus", "occurrenceCount",
        "servedAirportCount", "runwayEndAssociationCount", "sourceTable",
        "sourceRowIds",
    },
    "procedure_join_candidates.csv": {
        "procedureKey", "procedureType", "bodyPathKey", "transitionPathKey",
        "bodyStartPointKey", "bodyEndPointKey", "transitionStartPointKey",
        "transitionEndPointKey", "joinStatus",
    },
    "procedure_direction_name_audit.csv": {
        "procedureKey", "procedureType", "procedurePathKey", "routeName",
        "routeNameFirstToken", "routeNameLastToken",
        "operationalStartRawPoint", "operationalEndRawPoint",
        "directionNameStatus",
    },
    "airway_direction_evidence.csv": {
        "airwayKey", "airwayPathKey", "fromOccurrenceKey",
        "toOccurrenceKey", "fromPointKey", "toPointKey", "fromPointSeq",
        "toPointSeq", "magCourse", "oppositeMagCourse",
        "minEnrouteAltFt", "minEnrouteAltOppositeFt", "gapFlag",
        "signalGapFlag", "dogleg", "sourceTable", "sourceRowId",
    },
    "procedure_variant_candidates.csv": {
        "variantCandidateKey", "procedureKey", "procedureType",
        "bodyPathKey", "transitionPathKey", "variantStatus",
    },
    "procedure_enroute_interface.csv": {
        "procedureKey", "procedureType", "bodyPathKey", "transitionPathKey",
        "interfacePointRole", "interfacePointKey", "interfaceRawPoint",
        "airwayOccurrenceCount", "airwayPathCount", "airwayCount",
        "interfaceStatus",
    },
}


def normalize(value):
    return "_".join(str(value or "").strip().upper().replace("/", "_").split())


def flag_active(value):
    return normalize(value) not in {"", "N", "NO", "0", "FALSE"}


def bool_text(value):
    return "true" if value else "false"


def read_csv(path, required_columns):
    if not path.exists():
        raise ValueError(f"Missing required CSV: {path}")
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or [])
        missing = sorted(required_columns - fields)
        if missing:
            raise ValueError(f"Missing required column(s) in {path.name}: {', '.join(missing)}")
        return list(reader)


def write_csv(path, columns, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def reset_output_dir(output_dir):
    output_dir = Path(output_dir)
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)


def load_reachability(reachability_dir):
    reachability_dir = Path(reachability_dir)
    return {
        filename: read_csv(reachability_dir / filename, columns)
        for filename, columns in REACHABILITY_REQUIRED.items()
    }


def endpoint_unresolved_detail(endpoints):
    rows = []
    for row in endpoints:
        start_missing = not row["operationalStartPointKey"]
        end_missing = not row["operationalEndPointKey"]
        if not start_missing and not end_missing:
            continue
        if start_missing and end_missing:
            roles = ["both"]
        elif start_missing:
            roles = ["operational_start"]
        else:
            roles = ["operational_end"]
        for role in roles:
            if role == "operational_end":
                occurrence = row["operationalEndOccurrenceKey"]
                raw = row["operationalEndRawPoint"]
                point = row["operationalEndPointKey"]
                status = row["operationalEndResolveStatus"]
            else:
                occurrence = row["operationalStartOccurrenceKey"]
                raw = row["operationalStartRawPoint"]
                point = row["operationalStartPointKey"]
                status = row["operationalStartResolveStatus"]
            rows.append({
                "procedureKey": row["procedureKey"],
                "procedureType": row["procedureType"],
                "procedurePathKey": row["procedurePathKey"],
                "routePortionType": row["routePortionType"],
                "routeName": row["routeName"],
                "endpointRole": role,
                "endpointOccurrenceKey": occurrence,
                "endpointRawPoint": raw,
                "endpointPointKey": point,
                "endpointResolveStatus": status,
                "occurrenceCount": row["occurrenceCount"],
                "servedAirportCount": row["servedAirportCount"],
                "runwayEndAssociationCount": row["runwayEndAssociationCount"],
                "sourceTable": row["sourceTable"],
                "sourceRowIds": row["sourceRowIds"],
            })
    rows.sort(key=lambda item: (item["procedureKey"], item["procedurePathKey"], item["endpointRole"]))
    return rows


def endpoint_maps(endpoints):
    return {row["procedurePathKey"]: row for row in endpoints}


def join_mismatch_detail(joins, endpoints_by_path):
    rows = []
    for row in joins:
        if row["joinStatus"] != "no_shared_join_point":
            continue
        body = endpoints_by_path[row["bodyPathKey"]]
        transition = endpoints_by_path[row["transitionPathKey"]]
        if row["procedureType"] == "DP":
            body_raw = body["operationalEndRawPoint"]
            transition_raw = transition["operationalStartRawPoint"]
            body_join_key = row["bodyEndPointKey"]
            transition_join_key = row["transitionStartPointKey"]
        else:
            body_raw = body["operationalStartRawPoint"]
            transition_raw = transition["operationalEndRawPoint"]
            body_join_key = row["bodyStartPointKey"]
            transition_join_key = row["transitionEndPointKey"]
        rows.append({
            "procedureKey": row["procedureKey"],
            "procedureType": row["procedureType"],
            "bodyPathKey": row["bodyPathKey"],
            "transitionPathKey": row["transitionPathKey"],
            "bodyRouteName": body["routeName"],
            "transitionRouteName": transition["routeName"],
            "bodyStartRawPoint": body["operationalStartRawPoint"],
            "bodyEndRawPoint": body["operationalEndRawPoint"],
            "transitionStartRawPoint": transition["operationalStartRawPoint"],
            "transitionEndRawPoint": transition["operationalEndRawPoint"],
            "bodyJoinPointKey": body_join_key,
            "transitionJoinPointKey": transition_join_key,
            "bodyJoinRawPoint": body_raw,
            "transitionJoinRawPoint": transition_raw,
            "normalizedBodyJoinRawPoint": normalize(body_raw),
            "normalizedTransitionJoinRawPoint": normalize(transition_raw),
            "rawPointNamesEqual": bool_text(normalize(body_raw) == normalize(transition_raw)),
            "pointKeysEqual": bool_text(body_join_key == transition_join_key),
            "sourceTables": "|".join(sorted({body["sourceTable"], transition["sourceTable"]})),
            "sourceRowIds": "|".join(filter(None, [body["sourceRowIds"], transition["sourceRowIds"]])),
        })
    rows.sort(key=lambda item: (item["procedureKey"], item["bodyPathKey"], item["transitionPathKey"]))
    return rows


def direction_name_mismatch_detail(direction_rows, endpoints_by_path):
    rows = []
    for row in direction_rows:
        if row["directionNameStatus"] != "endpoint_name_mismatch":
            continue
        endpoint = endpoints_by_path[row["procedurePathKey"]]
        first = normalize(row["routeNameFirstToken"])
        last = normalize(row["routeNameLastToken"])
        start = normalize(row["operationalStartRawPoint"])
        end = normalize(row["operationalEndRawPoint"])
        start_matches = first == start
        end_matches = last == end
        first_format_related = token_related(first, start)
        last_format_related = token_related(last, end)
        if start_matches and end_matches:
            cause = "unknown"
        elif first_format_related or last_format_related:
            cause = "format_or_suffix_difference"
        elif start_matches and not end_matches:
            cause = "last_token_mismatch"
        elif end_matches and not start_matches:
            cause = "first_token_mismatch"
        elif not start_matches and not end_matches:
            cause = "both_tokens_mismatch"
        else:
            cause = "unknown"
        rows.append({
            "procedureKey": row["procedureKey"],
            "procedureType": row["procedureType"],
            "procedurePathKey": row["procedurePathKey"],
            "routeName": row["routeName"],
            "routeNameFirstToken": row["routeNameFirstToken"],
            "routeNameLastToken": row["routeNameLastToken"],
            "operationalStartRawPoint": row["operationalStartRawPoint"],
            "operationalEndRawPoint": row["operationalEndRawPoint"],
            "normalizedFirstToken": first,
            "normalizedLastToken": last,
            "normalizedStartRawPoint": start,
            "normalizedEndRawPoint": end,
            "startMatches": bool_text(start_matches),
            "endMatches": bool_text(end_matches),
            "possibleCause": cause,
            "sourceTable": endpoint["sourceTable"],
            "sourceRowIds": endpoint["sourceRowIds"],
        })
    rows.sort(key=lambda item: (item["procedureKey"], item["procedurePathKey"]))
    return rows


def token_related(left, right):
    if not left or not right or left == right:
        return False
    return left.startswith(right) or right.startswith(left) or left.endswith(right) or right.endswith(left) or left in right or right in left


def opposite_field_status(row):
    has_course = bool(row["oppositeMagCourse"])
    has_alt = bool(row["minEnrouteAltOppositeFt"])
    if has_course and has_alt:
        return "both_present"
    if has_course:
        return "course_only"
    if has_alt:
        return "opposite_alt_only"
    return "none"


def reverse_class(opposite_status, any_gap):
    has_opposite = opposite_status != "none"
    if has_opposite and any_gap:
        return "opposite_fields_with_gap"
    if has_opposite:
        return "opposite_fields_no_gap"
    if any_gap:
        return "no_opposite_fields_with_gap"
    return "no_opposite_fields_no_gap"


def airway_reverse_detail(airways):
    rows = []
    for row in airways:
        gap = flag_active(row["gapFlag"])
        signal_gap = flag_active(row["signalGapFlag"])
        dogleg = flag_active(row["dogleg"])
        any_gap = gap or signal_gap
        status = opposite_field_status(row)
        rows.append({
            "airwayKey": row["airwayKey"],
            "airwayPathKey": row["airwayPathKey"],
            "fromOccurrenceKey": row["fromOccurrenceKey"],
            "toOccurrenceKey": row["toOccurrenceKey"],
            "fromPointKey": row["fromPointKey"],
            "toPointKey": row["toPointKey"],
            "fromPointSeq": row["fromPointSeq"],
            "toPointSeq": row["toPointSeq"],
            "magCourse": row["magCourse"],
            "oppositeMagCourse": row["oppositeMagCourse"],
            "minEnrouteAltFt": row["minEnrouteAltFt"],
            "minEnrouteAltOppositeFt": row["minEnrouteAltOppositeFt"],
            "oppositeFieldStatus": status,
            "gapFlagRaw": row["gapFlag"],
            "gapFlagActive": bool_text(gap),
            "signalGapFlagRaw": row["signalGapFlag"],
            "signalGapFlagActive": bool_text(signal_gap),
            "doglegRaw": row["dogleg"],
            "doglegActive": bool_text(dogleg),
            "anyGapActive": bool_text(any_gap),
            "reverseEvidenceClass": reverse_class(status, any_gap),
            "sourceTable": row["sourceTable"],
            "sourceRowId": row["sourceRowId"],
        })
    rows.sort(key=lambda item: (item["airwayKey"], item["airwayPathKey"], item["fromPointSeq"], item["sourceRowId"]))
    return rows


def airway_reverse_summary(rows, validate_expected_counts):
    metrics = {
        "totalRows": len(rows),
        "oppositeAnyFieldRows": sum(1 for row in rows if row["oppositeFieldStatus"] != "none"),
        "oppositeBothFieldRows": sum(1 for row in rows if row["oppositeFieldStatus"] == "both_present"),
        "oppositeCourseOnlyRows": sum(1 for row in rows if row["oppositeFieldStatus"] == "course_only"),
        "oppositeAltitudeOnlyRows": sum(1 for row in rows if row["oppositeFieldStatus"] == "opposite_alt_only"),
        "noOppositeFieldRows": sum(1 for row in rows if row["oppositeFieldStatus"] == "none"),
        "gapFlagActiveRows": sum(1 for row in rows if row["gapFlagActive"] == "true"),
        "signalGapFlagActiveRows": sum(1 for row in rows if row["signalGapFlagActive"] == "true"),
        "anyGapActiveRows": sum(1 for row in rows if row["anyGapActive"] == "true"),
        "doglegActiveRows": sum(1 for row in rows if row["doglegActive"] == "true"),
        "oppositeFieldsWithGapRows": sum(1 for row in rows if row["reverseEvidenceClass"] == "opposite_fields_with_gap"),
        "noOppositeFieldsWithGapRows": sum(1 for row in rows if row["reverseEvidenceClass"] == "no_opposite_fields_with_gap"),
        "noOppositeFieldsNoGapRows": sum(1 for row in rows if row["reverseEvidenceClass"] == "no_opposite_fields_no_gap"),
    }
    if validate_expected_counts:
        validate_airway_reverse_identities(metrics)
    return [{"metric": key, "value": value} for key, value in metrics.items()]


def validate_airway_reverse_identities(metrics):
    checks = [
        (
            "totalRows = oppositeAnyFieldRows + noOppositeFieldRows",
            metrics["totalRows"],
            metrics["oppositeAnyFieldRows"] + metrics["noOppositeFieldRows"],
        ),
        (
            "oppositeAnyFieldRows = oppositeBothFieldRows + oppositeCourseOnlyRows + oppositeAltitudeOnlyRows",
            metrics["oppositeAnyFieldRows"],
            metrics["oppositeBothFieldRows"] + metrics["oppositeCourseOnlyRows"] + metrics["oppositeAltitudeOnlyRows"],
        ),
        (
            "noOppositeFieldRows = noOppositeFieldsWithGapRows + noOppositeFieldsNoGapRows",
            metrics["noOppositeFieldRows"],
            metrics["noOppositeFieldsWithGapRows"] + metrics["noOppositeFieldsNoGapRows"],
        ),
        (
            "anyGapActiveRows = oppositeFieldsWithGapRows + noOppositeFieldsWithGapRows",
            metrics["anyGapActiveRows"],
            metrics["oppositeFieldsWithGapRows"] + metrics["noOppositeFieldsWithGapRows"],
        ),
    ]
    errors = [
        f"{name}: left {left}, right {right}"
        for name, left, right in checks
        if left != right
    ]
    if errors:
        raise ValueError("Airway reverse evidence identity mismatch: " + "; ".join(errors))


def airway_no_opposite_grouped(rows):
    groups = defaultdict(list)
    for row in rows:
        if row["oppositeFieldStatus"] == "none":
            key = (
                row["airwayKey"], row["airwayPathKey"], row["anyGapActive"],
                row["gapFlagRaw"], row["signalGapFlagRaw"], row["doglegRaw"],
                row["sourceTable"],
            )
            groups[key].append(row)
    output = []
    for key, items in sorted(groups.items()):
        output.append({
            "airwayKey": key[0],
            "airwayPathKey": key[1],
            "anyGapActive": key[2],
            "gapFlagRaw": key[3],
            "signalGapFlagRaw": key[4],
            "doglegRaw": key[5],
            "sourceTable": key[6],
            "rowCount": len(items),
            "sampleFromPointKeys": "|".join(row["fromPointKey"] for row in items[:10]),
            "sampleToPointKeys": "|".join(row["toPointKey"] for row in items[:10]),
            "sampleSourceRowIds": "|".join(row["sourceRowId"] for row in items[:10]),
        })
    return output


def airway_no_opposite_endpoint_pattern(rows):
    groups = defaultdict(list)
    for row in rows:
        if row["oppositeFieldStatus"] != "none":
            continue
        from_kind = point_kind(row["fromPointKey"])
        to_kind = point_kind(row["toPointKey"])
        key = (
            from_kind,
            to_kind,
            bool_text("BOUNDARY_POINT" in {from_kind, to_kind}),
            row["anyGapActive"],
            row["doglegActive"],
            airway_prefix(row["airwayKey"]),
            airway_location(row["airwayPathKey"]),
        )
        groups[key].append(row)
    output = []
    for key, items in sorted(groups.items()):
        output.append({
            "fromPointKind": key[0],
            "toPointKind": key[1],
            "containsBoundaryPoint": key[2],
            "anyGapActive": key[3],
            "doglegActive": key[4],
            "airwayPrefix": key[5],
            "awyLocation": key[6],
            "rowCount": len(items),
            "airwayCount": len({row["airwayKey"] for row in items}),
            "airwayPathCount": len({row["airwayPathKey"] for row in items}),
            "sampleAirwayKeys": "|".join(sorted({row["airwayKey"] for row in items})[:10]),
            "sampleFromPointKeys": "|".join(row["fromPointKey"] for row in items[:10]),
            "sampleToPointKeys": "|".join(row["toPointKey"] for row in items[:10]),
            "sampleSourceRowIds": "|".join(row["sourceRowId"] for row in items[:10]),
        })
    return output


def airway_prefix(airway_key):
    ident = airway_key.split(":", 1)[-1] if ":" in airway_key else airway_key
    letters = "".join(ch for ch in ident if ch.isalpha()).upper()
    if letters in {"J", "Q", "T", "V", "M", "R"}:
        return letters
    return "OTHER"


def airway_location(airway_path_key):
    parts = airway_path_key.split(":")
    return parts[-1] if parts else ""


def point_kind(point_key):
    if not point_key:
        return "UNRESOLVED"
    if point_key.startswith("POINT:FIX:"):
        return "FIX"
    if point_key.startswith("POINT:NAVAID:"):
        return "NAVAID"
    if point_key.startswith("POINT:BOUNDARY"):
        return "BOUNDARY_POINT"
    return "OTHER"


def interface_detail(interfaces, variants):
    variant_by_key = {
        (row["procedureKey"], row["bodyPathKey"], row["transitionPathKey"]): row
        for row in variants
    }
    rows = []
    for row in interfaces:
        variant = variant_by_key[(row["procedureKey"], row["bodyPathKey"], row["transitionPathKey"])]
        complete = variant["variantStatus"] == "matched_body_transition"
        rows.append({
            "variantCandidateKey": variant["variantCandidateKey"],
            "variantStatus": variant["variantStatus"],
            "procedureKey": row["procedureKey"],
            "procedureType": row["procedureType"],
            "bodyPathKey": row["bodyPathKey"],
            "transitionPathKey": row["transitionPathKey"],
            "interfacePointRole": row["interfacePointRole"],
            "interfacePointKey": row["interfacePointKey"],
            "interfaceRawPoint": row["interfaceRawPoint"],
            "pointKind": point_kind(row["interfacePointKey"]),
            "airwayOccurrenceCount": row["airwayOccurrenceCount"],
            "airwayPathCount": row["airwayPathCount"],
            "airwayCount": row["airwayCount"],
            "interfaceStatus": row["interfaceStatus"],
            "isCompleteMatchedVariant": bool_text(complete),
            "dedupeProcedureTransitionPointKey": "|".join([row["procedureKey"], row["transitionPathKey"], row["interfacePointKey"]]),
            "dedupeProcedurePointKey": "|".join([row["procedureKey"], row["interfacePointKey"]]),
        })
    rows.sort(key=lambda item: item["variantCandidateKey"])
    return rows


def interface_summary(detail):
    scopes = {
        "variant_row": lambda row: row["variantCandidateKey"],
        "procedure_transition_point": lambda row: row["dedupeProcedureTransitionPointKey"],
        "procedure_point": lambda row: row["dedupeProcedurePointKey"],
        "category_distinct_point": lambda row: row["interfacePointKey"],
    }
    output = []
    for scope, key_func in scopes.items():
        groups = defaultdict(set)
        for row in detail:
            group_key = (
                row["procedureType"], row["variantStatus"],
                row["pointKind"], row["interfaceStatus"],
            )
            groups[group_key].add(key_func(row))
        for key, values in sorted(groups.items()):
            output.append({
                "scope": scope,
                "procedureType": key[0],
                "variantStatus": key[1],
                "pointKind": key[2],
                "interfaceStatus": key[3],
                "rowCount": len(values),
            })
    return output


def unique_interface_points(detail):
    grouped = defaultdict(list)
    for row in detail:
        if row["interfacePointKey"]:
            grouped[row["interfacePointKey"]].append(row)
    output = []
    for point_key, rows in sorted(grouped.items()):
        matched = [row for row in rows if row["variantStatus"] == "matched_body_transition"]
        incomplete = [row for row in rows if row["variantStatus"] != "matched_body_transition"]
        occurrence_count = consistent_count(point_key, rows, "airwayOccurrenceCount")
        path_count = consistent_count(point_key, rows, "airwayPathCount")
        airway_count = consistent_count(point_key, rows, "airwayCount")
        output.append({
            "interfacePointKey": point_key,
            "interfaceRawPoints": "|".join(sorted({row["interfaceRawPoint"] for row in rows if row["interfaceRawPoint"]})),
            "pointKind": point_kind(point_key),
            "usedByDP": bool_text(any(row["procedureType"] == "DP" for row in rows)),
            "usedBySTAR": bool_text(any(row["procedureType"] == "STAR" for row in rows)),
            "procedureCount": len({row["procedureKey"] for row in rows}),
            "matchedProcedureCount": len({row["procedureKey"] for row in matched}),
            "matchedVariantCount": len(matched),
            "incompleteVariantCount": len(incomplete),
            "connectedToAirwayNetwork": bool_text(occurrence_count > 0),
            "airwayOccurrenceCount": occurrence_count,
            "airwayPathCount": path_count,
            "airwayCount": airway_count,
            "procedureKeys": "|".join(sorted({row["procedureKey"] for row in rows})),
            "variantStatuses": "|".join(sorted({row["variantStatus"] for row in rows})),
        })
    return output


def consistent_count(point_key, rows, field):
    values = set()
    for row in rows:
        raw = row.get(field, "")
        if raw == "":
            continue
        try:
            values.add(int(raw))
        except ValueError as exc:
            raise ValueError(
                f"Non-integer {field} for {point_key}: {raw}"
            ) from exc
    if not values:
        return 0
    if len(values) > 1:
        raise ValueError(
            f"Conflicting {field} for {point_key}: "
            + "|".join(str(value) for value in sorted(values))
        )
    return next(iter(values))


def procedure_interface_summary(detail):
    grouped = defaultdict(list)
    for row in detail:
        grouped[row["procedureKey"]].append(row)
    output = []
    for proc_key, rows in sorted(grouped.items()):
        matched = [row for row in rows if row["variantStatus"] == "matched_body_transition"]
        connected_matched = [
            row for row in matched
            if row["interfaceStatus"] == "connected_to_airway_network"
        ]
        not_connected_matched = [
            row for row in matched
            if row["interfaceStatus"] == "not_found_in_airway_network"
        ]
        unique_points = {row["interfacePointKey"] for row in rows if row["interfacePointKey"]}
        connected_points = {
            row["interfacePointKey"] for row in rows
            if row["interfacePointKey"]
            and row["interfaceStatus"] == "connected_to_airway_network"
        }
        output.append({
            "procedureKey": proc_key,
            "procedureType": rows[0]["procedureType"],
            "variantCount": len(rows),
            "matchedVariantCount": len(matched),
            "connectedMatchedVariantCount": len(connected_matched),
            "notConnectedMatchedVariantCount": len(not_connected_matched),
            "uniqueInterfacePointCount": len(unique_points),
            "connectedInterfacePointCount": len(connected_points),
            "hasAnyMatchedVariant": bool_text(bool(matched)),
            "hasAnyConnectedMatchedVariant": bool_text(bool(connected_matched)),
            "allMatchedVariantsUnconnected": bool_text(bool(matched) and not connected_matched),
            "onlyIncompleteVariants": bool_text(not matched),
        })
    return output


def data_gap_summary(unresolved, joins, directions, airway_rows, interface_detail_rows, procedure_summary, unique_points):
    def count_airway(class_name):
        return sum(1 for row in airway_rows if row["reverseEvidenceClass"] == class_name)

    dp_matched = [row for row in interface_detail_rows if row["procedureType"] == "DP" and row["variantStatus"] == "matched_body_transition"]
    star_matched = [row for row in interface_detail_rows if row["procedureType"] == "STAR" and row["variantStatus"] == "matched_body_transition"]
    matched_unique = [row for row in unique_points if int(row["matchedVariantCount"]) > 0]
    return [
        {"metric": "procedure_endpoint_unresolved_rows", "value": len(unresolved)},
        {"metric": "procedure_join_no_shared_rows", "value": len(joins)},
        {"metric": "procedure_direction_name_mismatch_rows", "value": len(directions)},
        {"metric": "airway_no_opposite_rows", "value": sum(1 for row in airway_rows if row["oppositeFieldStatus"] == "none")},
        {"metric": "airway_no_opposite_with_gap_rows", "value": count_airway("no_opposite_fields_with_gap")},
        {"metric": "airway_no_opposite_without_gap_rows", "value": count_airway("no_opposite_fields_no_gap")},
        {"metric": "airway_opposite_with_gap_rows", "value": count_airway("opposite_fields_with_gap")},
        {"metric": "gap_flag_active_rows", "value": sum(1 for row in airway_rows if row["gapFlagActive"] == "true")},
        {"metric": "signal_gap_flag_active_rows", "value": sum(1 for row in airway_rows if row["signalGapFlagActive"] == "true")},
        {"metric": "dogleg_active_rows", "value": sum(1 for row in airway_rows if row["doglegActive"] == "true")},
        {"metric": "dp_matched_variant_rows", "value": len(dp_matched)},
        {"metric": "dp_matched_variant_connected_rows", "value": sum(1 for row in dp_matched if row["interfaceStatus"] == "connected_to_airway_network")},
        {"metric": "dp_matched_variant_not_connected_rows", "value": sum(1 for row in dp_matched if row["interfaceStatus"] == "not_found_in_airway_network")},
        {"metric": "star_matched_variant_rows", "value": len(star_matched)},
        {"metric": "star_matched_variant_connected_rows", "value": sum(1 for row in star_matched if row["interfaceStatus"] == "connected_to_airway_network")},
        {"metric": "star_matched_variant_not_connected_rows", "value": sum(1 for row in star_matched if row["interfaceStatus"] == "not_found_in_airway_network")},
        {"metric": "dp_procedures_with_connected_matched_variant", "value": sum(1 for row in procedure_summary if row["procedureType"] == "DP" and row["hasAnyConnectedMatchedVariant"] == "true")},
        {"metric": "dp_procedures_all_matched_variants_unconnected", "value": sum(1 for row in procedure_summary if row["procedureType"] == "DP" and row["allMatchedVariantsUnconnected"] == "true")},
        {"metric": "star_procedures_with_connected_matched_variant", "value": sum(1 for row in procedure_summary if row["procedureType"] == "STAR" and row["hasAnyConnectedMatchedVariant"] == "true")},
        {"metric": "star_procedures_all_matched_variants_unconnected", "value": sum(1 for row in procedure_summary if row["procedureType"] == "STAR" and row["allMatchedVariantsUnconnected"] == "true")},
        {"metric": "global_unique_interface_point_count", "value": len(unique_points)},
        {"metric": "global_unique_matched_interface_point_count", "value": len(matched_unique)},
        {"metric": "global_unique_connected_matched_interface_point_count", "value": sum(1 for row in matched_unique if row["connectedToAirwayNetwork"] == "true")},
        {"metric": "global_unique_unconnected_matched_interface_point_count", "value": sum(1 for row in matched_unique if row["connectedToAirwayNetwork"] == "false")},
    ]


def reset_output_dir(output_dir):
    output_dir = Path(output_dir)
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)


def analyze_reachability_data_gaps(clean_dir, reachability_dir, output_dir, validate_expected_counts=True):
    # The clean directory is not read by this analysis stage; it is checked only
    # to ensure the audit inputs are tied to an existing clean data set.
    if not Path(clean_dir).exists():
        raise ValueError(f"Missing clean dir: {clean_dir}")
    data = load_reachability(reachability_dir)
    reset_output_dir(output_dir)
    output_dir = Path(output_dir)

    endpoints = data["procedure_path_endpoints.csv"]
    endpoint_by_path = {row["procedurePathKey"]: row for row in endpoints}

    unresolved = endpoint_unresolved_detail(endpoints)
    joins = join_mismatch_detail(data["procedure_join_candidates.csv"], endpoint_by_path)
    directions = direction_name_mismatch_detail(data["procedure_direction_name_audit.csv"], endpoint_by_path)
    airway = airway_reverse_detail(data["airway_direction_evidence.csv"])
    variants = data["procedure_variant_candidates.csv"]
    interface_rows = interface_detail(data["procedure_enroute_interface.csv"], variants)
    interface_summary_rows = interface_summary(interface_rows)
    procedure_summary_rows = procedure_interface_summary(interface_rows)
    unique_point_rows = unique_interface_points(interface_rows)

    write_csv(output_dir / "procedure_endpoint_unresolved_detail.csv", UNRESOLVED_ENDPOINT_COLUMNS, unresolved)
    write_csv(output_dir / "procedure_join_mismatch_detail.csv", JOIN_MISMATCH_COLUMNS, joins)
    write_csv(output_dir / "procedure_direction_name_mismatch_detail.csv", DIRECTION_MISMATCH_COLUMNS, directions)
    write_csv(output_dir / "airway_reverse_evidence_detail.csv", AIRWAY_REVERSE_COLUMNS, airway)
    write_csv(output_dir / "airway_reverse_evidence_summary.csv", SUMMARY_COLUMNS, airway_reverse_summary(airway, validate_expected_counts))
    write_csv(output_dir / "airway_no_opposite_grouped.csv", AIRWAY_NO_OPPOSITE_GROUP_COLUMNS, airway_no_opposite_grouped(airway))
    write_csv(output_dir / "airway_no_opposite_endpoint_pattern.csv", AIRWAY_NO_OPPOSITE_ENDPOINT_PATTERN_COLUMNS, airway_no_opposite_endpoint_pattern(airway))
    write_csv(output_dir / "procedure_interface_gap_detail.csv", INTERFACE_DETAIL_COLUMNS, interface_rows)
    write_csv(output_dir / "procedure_interface_gap_summary.csv", INTERFACE_SUMMARY_COLUMNS, interface_summary_rows)
    write_csv(output_dir / "procedure_interface_procedure_summary.csv", PROCEDURE_INTERFACE_SUMMARY_COLUMNS, procedure_summary_rows)
    write_csv(output_dir / "unique_interface_points.csv", UNIQUE_INTERFACE_POINT_COLUMNS, unique_point_rows)
    write_csv(output_dir / "reachability_data_gap_summary.csv", SUMMARY_COLUMNS, data_gap_summary(unresolved, joins, directions, airway, interface_rows, procedure_summary_rows, unique_point_rows))

    return {
        "procedure_endpoint_unresolved_rows": len(unresolved),
        "procedure_join_no_shared_rows": len(joins),
        "procedure_direction_name_mismatch_rows": len(directions),
        "airway_no_opposite_rows": sum(1 for row in airway if row["oppositeFieldStatus"] == "none"),
    }

def parse_args():
    parser = argparse.ArgumentParser(description="Analyze reachability audit data gaps.")
    parser.add_argument("--clean-dir", default=Path("data/clean"), type=Path)
    parser.add_argument("--reachability-dir", default=Path("data/audit/reachability"), type=Path)
    parser.add_argument("--output-dir", default=Path("data/audit/reachability_gaps"), type=Path)
    return parser.parse_args()


def main():
    args = parse_args()
    summary = analyze_reachability_data_gaps(
        args.clean_dir,
        args.reachability_dir,
        args.output_dir,
    )
    for key in sorted(summary):
        print(f"{key}: {summary[key]}")


if __name__ == "__main__":
    main()
