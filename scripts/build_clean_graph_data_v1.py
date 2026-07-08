import argparse
import csv
import re
from collections import Counter, defaultdict
from pathlib import Path


SOURCE_CYCLE = "2026-05-14"


COMMON = ("sourceCycle", "sourceTable", "sourceRowId")

AIRPORT_COLUMNS = (
    "airportKey", "arptId", "icaoId", "siteNo", "siteTypeCode",
    "airportName", "city", "stateCode", "countryCode", "regionCode", "lat",
    "lon", "elevationFt", "airportStatus", "facilityUseCode",
    "towerTypeCode", "notamId", "notamFlag", "responsibleArtcc",
    "artccName", *COMMON,
)

RUNWAY_COLUMNS = (
    "runwayKey", "arptId", "rwyId", "lengthFt", "widthFt",
    "surfaceTypeCode", "condition", "runwayLightCode", "pcn",
    "grossWeightSw", "grossWeightDw", "grossWeightDtw", "grossWeightDdtw",
    *COMMON,
)

RUNWAY_END_COLUMNS = (
    "runwayEndKey", "arptId", "rwyId", "rwyEndId", "trueAlignment",
    "ilsType", "lat", "lon", "runwayEndElevationFt",
    "displacedThresholdLength", "touchdownZoneElevationFt", "vgsiCode",
    "approachLightSystemCode", "runwayEndLightsFlag", "toraFt", "todaFt",
    "asdaFt", "ldaFt", *COMMON,
)

ROUTE_POINT_COLUMNS = (
    "pointKey", "pointType", "pointId", "name", "icaoRegionCode",
    "stateCode", "countryCode", "lat", "lon", "fixUseCode", "artccIdHigh",
    "artccIdLow", "minimumReceptionAltitudeFt", "compulsory", "charts",
    "navId", "navType", "navStatus", "city", "regionCode", "elevationFt",
    "freq", "chan", "nasUseFlag", "publicUseFlag", "operatingHours",
    "highAltArtccId", "lowAltArtccId", "notamId", "restrictionFlag",
    "rawName", "normalizedName", "boundaryType", "adjacentCountry",
    "boundaryIndex", *COMMON,
)

AIRWAY_COLUMNS = (
    "airwayKey", "awyId", "awyDesignation", "regulatory", "remark",
    "airwayString", "updateDate", *COMMON,
)

AIRWAY_PATH_COLUMNS = (
    "airwayPathKey", "airwayKey", "awyId", "awyLocation",
    "awyDesignation", "airwayString", *COMMON,
)

AIRWAY_OCCURRENCE_COLUMNS = (
    "airwayOccurrenceKey", "airwayPathKey", "awyId", "awyLocation",
    "pointSeq", "rawFromPoint", "rawFromPointType", "rawToPoint",
    "rawNextMeaPoint", "resolvedPointKey", "resolveStatus",
    "occurrenceRole", *COMMON,
)

PROCEDURE_COLUMNS = (
    "procedureKey", "procedureType", "procedureName", "computerCode",
    "amendmentNo", "artcc", "effectiveDate", "rnavFlag",
    "servedAirportRaw", "graphicalType", *COMMON,
)

PROCEDURE_PATH_COLUMNS = (
    "procedurePathKey", "procedureKey", "procedureType",
    "routePortionType", "routeName", "bodySeq", "transitionComputerCode",
    "sourceAggregation", "sourceRowIds", "sourceRowCount", *COMMON,
)

PROCEDURE_OCCURRENCE_COLUMNS = (
    "procedureOccurrenceKey", "procedurePathKey", "procedureKey",
    "procedureType", "pointSeq", "rawPoint", "rawPointType",
    "nextPointRaw", "arptRwyAssoc", "resolvedPointKey", "resolveStatus",
    *COMMON,
)

TEMPLATE_COLUMNS = (
    "templateKey", "templateType", "originRaw", "destinationRaw",
    "originCity", "destinationCity", "pfrTypeCode", "routeNo",
    "specialAreaDesc", "altitudeDescription", "aircraft", "hours",
    "directionDescription", "designator", "narType", "inlandFacilityFix",
    "coastalFix", "destinationDesc", "routeString", "codedRouteCode",
    "departureFixRaw", "departureCenter", "arrivalCenter", "throughCenters",
    "coordinationRequired", "play", "navigationEquipment", "lengthNm",
    "parseStatus", *COMMON,
)

TEMPLATE_PATH_COLUMNS = (
    "templatePathKey", "templateKey", "templateType", "routeString",
    *COMMON,
)

TEMPLATE_TOKEN_COLUMNS = (
    "templateTokenKey", "templatePathKey", "templateKey", "segmentSeq",
    "segValueRaw", "segType", "navType", "nextSegRaw", "resolvedRefKey",
    "resolvedRefType", "resolveStatus", *COMMON,
)

REL_COLUMNS = (
    "fromKey", "toKey", "sourceCycle", "sourceTable", "sourceRowId",
    "resolveStatus", "confidence",
)

RESOLVE_REL_COLUMNS = (
    "fromKey", "toKey", "rawValue", "normalizedValue", "resolveMethod",
    "resolveStatus", "confidence", "sourceCycle", "sourceTable",
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

NEXT_PROCEDURE_COLUMNS = (
    "fromKey", "toKey", "sourceNextPointRaw", "sequenceCheckStatus",
    "directionStatus", "sourceCycle", "sourceTable", "sourceRowId",
)

TEMPLATE_REF_COLUMNS = (
    "fromKey", "toKey", "refType", "rawValue", "normalizedValue",
    "resolveMethod", "resolveStatus", "confidence", "sourceCycle",
    "sourceTable", "sourceRowId",
)

AUDIT_DUPLICATE_COLUMNS = (
    "sourceTable", "keyType", "key", "count", "sourceRowIds",
)
AUDIT_UNRESOLVED_COLUMNS = (
    "sourceTable", "sourceRowId", "sourceObjectKey", "rawValue",
    "normalizedValue", "referenceType", "resolveStatus", "reason",
)
AUDIT_REJECTED_COLUMNS = (
    "sourceTable", "sourceRowId", "key", "reason",
)
AUDIT_SEQUENCE_COLUMNS = (
    "sourceTable", "pathKey", "issueType", "detail",
)
AUDIT_SUMMARY_COLUMNS = ("metric", "value")

NAVAID_GROUP_ANALYSIS_COLUMNS = (
    "navId", "navType", "groupSize", "sourceRowIds", "distinctNameCount",
    "nameList", "distinctCityCount", "cityList", "distinctStateCount",
    "stateList", "distinctCountryCount", "countryList", "distinctFreqCount",
    "freqList", "distinctChanCount", "chanList", "latLonList",
    "navStatusList", "nasUseFlagList", "publicUseFlagList",
    "appearsInAwySegCount", "appearsInDpRteCount", "appearsInStarRteCount",
    "appearsInPfrSegCount", "preliminaryPattern",
)

NAVAID_GROUP_DETAIL_COLUMNS = (
    "navId", "navType", "sourceRowId", "name", "city", "stateCode",
    "countryCode", "regionCode", "lat", "lon", "freq", "chan",
    "navStatus", "nasUseFlag", "publicUseFlag", "highAltArtccId",
    "lowAltArtccId", "legacyNavIdTypeKey", "currentPointKey",
)

NAVAID_REFERENCE_AMBIGUITY_COLUMNS = (
    "sourceTable", "sourceRowId", "sourceObjectKey", "rawValue",
    "rawNavType", "contextStateCode", "contextCountryCode",
    "contextIcaoRegionCode", "candidateCountByNavIdType",
    "candidatePointKeys", "candidateSourceRowIds", "currentResolvedPointKey",
    "currentResolveStatus", "ambiguityReason",
)

NAVAID_DUPLICATE_GROUP_REVIEW_COLUMNS = NAVAID_GROUP_ANALYSIS_COLUMNS + (
    "nameConflict", "cityConflict", "stateConflict", "countryConflict",
    "freqConflict", "coordConflict", "referencedInAnyRouteData",
)


def clean(value):
    value = str(value or "").strip()
    if value.upper() in {"", "NAN", "NONE", "NULL"}:
        return ""
    return value


def clean_id(value):
    return clean(value).upper()


def key_part(value):
    value = clean_id(value)
    value = re.sub(r"\s+", "_", value)
    value = re.sub(r"[^A-Z0-9_.:+/-]+", "_", value)
    return value.strip("_")


def source_props(table, row):
    return {
        "sourceCycle": SOURCE_CYCLE,
        "sourceTable": table,
        "sourceRowId": row.get("_sourceRowId", row.get("sourceRowId", "")),
    }


def read_table(input_dir, filename):
    path = Path(input_dir) / filename
    if not path.exists():
        return []
    table = path.stem.upper()
    with path.open(encoding="cp1252", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = []
        for index, raw in enumerate(reader, start=2):
            row = {clean(key).upper(): clean(value) for key, value in raw.items()}
            row["_sourceRowId"] = str(index)
            row["_sourceTable"] = table
            rows.append(row)
        return rows


def write_csv(path, columns, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def numeric_seq(value):
    try:
        return int(float(clean(value)))
    except ValueError:
        return 0


def join_key(*parts):
    return ":".join(key_part(part) for part in parts)


def airport_key(arpt_id):
    return f"AIRPORT:{key_part(arpt_id)}"


def runway_key(arpt_id, rwy_id):
    return f"RUNWAY:{key_part(arpt_id)}:{key_part(rwy_id)}"


def runway_end_key(arpt_id, rwy_id, rwy_end_id):
    return f"RWYEND:{key_part(arpt_id)}:{key_part(rwy_id)}:{key_part(rwy_end_id)}"


def fix_key(fix_id, icao_region_code):
    return f"POINT:FIX:{key_part(fix_id)}:{key_part(icao_region_code)}"


def navaid_key(row):
    return join_key(
        "POINT", "NAVAID", row.get("NAV_ID"), row.get("NAV_TYPE"),
        row.get("COUNTRY_CODE"), row.get("STATE_CODE"), row.get("CITY"),
    )


def airway_key(awy_id):
    return f"AIRWAY:{key_part(awy_id)}"


def airway_path_key(awy_id, awy_location):
    return f"AIRWAY_PATH:{key_part(awy_id)}:{key_part(awy_location)}"


def airway_occurrence_key(awy_id, awy_location, point_seq):
    return f"AWY_OCC:{key_part(awy_id)}:{key_part(awy_location)}:{key_part(point_seq)}"


def procedure_key(procedure_type, code, row):
    code_part = key_part(code)
    if procedure_type == "DP" and code_part == "NOT_ASSIGNED":
        return join_key(
            "PROCEDURE", "DP", "NOT_ASSIGNED", row.get("DP_NAME"),
            row.get("ARTCC"), row.get("AMENDMENT_NO"),
        )
    return f"PROCEDURE:{procedure_type}:{code_part}"


def procedure_path_key(procedure_key_value, row):
    return join_key(
        "PROC_PATH", procedure_key_value, row.get("ROUTE_PORTION_TYPE"),
        row.get("ROUTE_NAME"), row.get("BODY_SEQ"),
        row.get("TRANSITION_COMPUTER_CODE"),
    )


def procedure_occurrence_key(path_key, point_seq):
    return f"PROC_OCC:{path_key}:{key_part(point_seq)}"


def pfr_template_key(row):
    return join_key(
        "TEMPLATE", "PFR", row.get("ORIGIN_ID"), row.get("DSTN_ID"),
        row.get("PFR_TYPE_CODE"), row.get("ROUTE_NO"),
    )


def cdr_template_key(row):
    return f"TEMPLATE:CDR:{key_part(row.get('RCODE'))}"


def template_path_key(template_key):
    return f"TEMPLATE_PATH:{template_key}:MAIN"


def template_token_key(template_key, seq):
    return f"TEMPLATE_TOKEN:{template_key}:{key_part(seq)}"


def duplicate_audit(table, key_type, rows_and_keys):
    counts = Counter(key for _, key in rows_and_keys if key)
    row_ids = defaultdict(list)
    for row, key in rows_and_keys:
        if key and counts[key] > 1:
            row_ids[key].append(row.get("_sourceRowId", ""))
    return [
        {
            "sourceTable": table,
            "keyType": key_type,
            "key": key,
            "count": counts[key],
            "sourceRowIds": "|".join(ids),
        }
        for key, ids in sorted(row_ids.items())
    ]


def sorted_values(values):
    return sorted({clean(value) for value in values if clean(value)})


def pipe(values):
    return "|".join(sorted_values(values))


def lat_lon(row):
    lat = clean(row.get("LAT_DECIMAL"))
    lon = clean(row.get("LONG_DECIMAL"))
    return f"{lat},{lon}" if lat or lon else ""


def navaid_group_pattern(rows):
    if len(rows) == 1:
        return "single_record"
    names = sorted_values(row.get("NAME") for row in rows)
    cities = sorted_values(row.get("CITY") for row in rows)
    states = sorted_values(row.get("STATE_CODE") for row in rows)
    freqs = sorted_values(row.get("FREQ") for row in rows)
    coords = sorted_values(lat_lon(row) for row in rows)
    if not coords or not states or not cities:
        return "same_id_type_missing_location"
    if len(names) == len(cities) == len(coords) == 1:
        return "same_name_same_city_same_coord"
    if len(freqs) > 1:
        return "same_id_type_different_freq"
    if len(states) > 1:
        return "same_id_type_different_state"
    if len(cities) > 1:
        return "same_id_type_different_city"
    return "insufficient_fields"


def procedure_key_for_rte_row(proc_type, row, procedure_lookup):
    if proc_type == "DP":
        code = key_part(row.get("DP_COMPUTER_CODE"))
        name = key_part(row.get("DP_NAME"))
        artcc = key_part(row.get("ARTCC"))
        return procedure_lookup.get(
            (proc_type, code, name, artcc), f"PROCEDURE:DP:{code}"
        )
    return f"PROCEDURE:STAR:{key_part(row.get('STAR_COMPUTER_CODE'))}"


def source_object_key_for_reference(table, row, procedure_lookup=None):
    procedure_lookup = procedure_lookup or {}
    if table == "AWY_SEG_ALT":
        return airway_occurrence_key(
            row.get("AWY_ID"), row.get("AWY_LOCATION"), row.get("POINT_SEQ")
        )
    if table == "DP_RTE":
        proc_key = procedure_key_for_rte_row("DP", row, procedure_lookup)
        return procedure_occurrence_key(procedure_path_key(proc_key, row), row.get("POINT_SEQ"))
    if table == "STAR_RTE":
        proc_key = procedure_key_for_rte_row("STAR", row, procedure_lookup)
        return procedure_occurrence_key(procedure_path_key(proc_key, row), row.get("POINT_SEQ"))
    if table == "PFR_SEG":
        return template_token_key(pfr_template_key(row), row.get("SEGMENT_SEQ"))
    return ""


def is_navaid_reference(raw_type):
    return key_part(raw_type) in {
        "NAVAID", "VOR", "VOR/DME", "VORTAC", "TACAN", "NDB", "DME",
    }


def sequence_sort_key(item):
    seq = clean(item.get("pointSeq") or item.get("POINT_SEQ"))
    try:
        return 0, int(float(seq))
    except ValueError:
        return 1, seq


def sequence_issue(table, path_key, issue_type, **detail):
    return {
        "sourceTable": table,
        "pathKey": path_key,
        "issueType": issue_type,
        "detail": ";".join(f"{key}={value}" for key, value in detail.items()),
    }


def audit_path_sequence(rows, table, path_key, point_col, next_col):
    issues = []
    seen = defaultdict(list)
    for row in rows:
        seq = clean(row.get("POINT_SEQ"))
        if not seq:
            issues.append(
                sequence_issue(
                    table, path_key, "empty_point_seq",
                    sourceRowId=row.get("_sourceRowId", ""),
                )
            )
            continue
        try:
            float(seq)
        except ValueError:
            issues.append(
                sequence_issue(
                    table, path_key, "non_numeric_point_seq",
                    sourceRowId=row.get("_sourceRowId", ""),
                    pointSeq=seq,
                )
            )
        seen[seq].append(row.get("_sourceRowId", ""))
    for seq, row_ids in sorted(seen.items()):
        if len(row_ids) > 1:
            issues.append(
                sequence_issue(
                    table, path_key, "duplicate_point_seq",
                    pointSeq=seq, sourceRowIds="|".join(row_ids),
                )
            )

    ordered = sorted(rows, key=sequence_sort_key)
    for current, nxt in zip(ordered, ordered[1:]):
        current_next = clean_id(current.get(next_col))
        next_point = clean_id(nxt.get(point_col))
        if current_next != next_point:
            if table == "AWY_SEG_ALT":
                issues.append(
                    sequence_issue(
                        table, path_key, "airway_to_next_from_mismatch",
                        currentSourceRowId=current.get("_sourceRowId", ""),
                        nextSourceRowId=nxt.get("_sourceRowId", ""),
                        currentToPoint=current.get(next_col, ""),
                        nextFromPoint=nxt.get(point_col, ""),
                        currentPointSeq=current.get("POINT_SEQ", ""),
                        nextPointSeq=nxt.get("POINT_SEQ", ""),
                    )
                )
            else:
                issues.append(
                    sequence_issue(
                        table, path_key, "procedure_next_point_mismatch",
                        currentSourceRowId=current.get("_sourceRowId", ""),
                        nextSourceRowId=nxt.get("_sourceRowId", ""),
                        currentNextPoint=current.get(next_col, ""),
                        nextPoint=nxt.get(point_col, ""),
                        currentPointSeq=current.get("POINT_SEQ", ""),
                        nextPointSeq=nxt.get("POINT_SEQ", ""),
                    )
                )
    return issues


def one_to_one_map(rows, key_func):
    counts = Counter(key_func(row) for row in rows)
    return {
        key_func(row): row
        for row in rows
        if key_func(row) and counts[key_func(row)] == 1
    }


def build_route_point_indexes(route_points):
    fix_exact = {}
    fixes_by_id = defaultdict(list)
    navaid_exact = defaultdict(list)
    navaids_by_id_type = defaultdict(list)
    navaids_by_id = defaultdict(list)

    for point in route_points:
        if point["pointType"] == "FIX":
            key = point["pointKey"]
            fix_exact[(point["pointId"], point["icaoRegionCode"])] = key
            fixes_by_id[point["pointId"]].append(key)
        elif point["pointType"] == "NAVAID":
            key = point["pointKey"]
            navaid_exact[
                (
                    point["navId"], point["navType"], point["countryCode"],
                    point["stateCode"],
                )
            ].append(key)
            navaids_by_id_type[(point["navId"], point["navType"])].append(key)
            navaids_by_id[point["navId"]].append(key)

    return {
        "fix_exact": fix_exact,
        "fixes_by_id": fixes_by_id,
        "navaid_exact": navaid_exact,
        "navaids_by_id_type": navaids_by_id_type,
        "navaids_by_id": navaids_by_id,
    }


def resolve_route_point(raw_value, raw_type, context, indexes):
    value = key_part(raw_value)
    raw_type = key_part(raw_type)
    if not value:
        return "", "unresolved", "empty_value", "low"

    if raw_type in {"FIX", "WAYPOINT"}:
        key = indexes["fix_exact"].get((value, key_part(context.get("ICAO_REGION_CODE"))))
        if key:
            return key, "resolved_fix", "fix_id_icao_region", "high"
        candidates = indexes["fixes_by_id"].get(value, [])
        if len(candidates) == 1:
            return candidates[0], "resolved_fix", "unique_fix_id", "medium"
        return "", "unresolved", "missing_or_ambiguous_fix", "low"

    nav_type = raw_type
    if nav_type in {"VOR/DME", "VORTAC", "TACAN", "NDB", "DME", "VOR"}:
        state = key_part(context.get("STATE_CODE"))
        country = key_part(context.get("COUNTRY_CODE"))
        exact = indexes["navaid_exact"].get((value, nav_type, country, state), [])
        if len(exact) == 1:
            return exact[0], "resolved_navaid", "navaid_id_type_country_state", "high"
        candidates = indexes["navaids_by_id_type"].get((value, nav_type), [])
        if len(candidates) == 1:
            return candidates[0], "resolved_navaid", "unique_navaid_id_type", "medium"
        return "", "unresolved", "missing_or_ambiguous_navaid", "low"

    candidates = indexes["fixes_by_id"].get(value, [])
    if len(candidates) == 1:
        return candidates[0], "resolved_fix", "unique_id_fallback", "medium"
    nav_candidates = indexes["navaids_by_id"].get(value, [])
    if len(nav_candidates) == 1:
        return nav_candidates[0], "resolved_navaid", "unique_id_fallback", "medium"
    return "", "unresolved", "missing_or_ambiguous_point", "low"


def is_boundary_point(raw_value, row):
    text = f"{clean_id(raw_value)} {clean_id(row.get('COUNTRY_CODE'))}"
    return any(token in text for token in ("CANAD", "MEXIC", "BOUNDARY", "BORDER"))


def boundary_key(raw_value):
    return f"POINT:BOUNDARY:{key_part(raw_value)}"


def base_rel(from_key, to_key, table, row, status="resolved", confidence="high"):
    return {
        "fromKey": from_key,
        "toKey": to_key,
        "resolveStatus": status,
        "confidence": confidence,
        **source_props(table, row),
    }


def amendment_number(value):
    words = {
        "ONE": "1", "TWO": "2", "THREE": "3", "FOUR": "4", "FIVE": "5",
        "SIX": "6", "SEVEN": "7", "EIGHT": "8", "NINE": "9", "TEN": "10",
        "ELEVEN": "11", "TWELVE": "12",
    }
    value = key_part(value)
    return words.get(value, value if value.isdigit() else "")


def add_procedure_alias(aliases, procedure_type, alias, procedure_key_value):
    alias = key_part(alias)
    if alias:
        aliases[(procedure_type, alias)].add(procedure_key_value)


def resolve_procedure_alias(aliases, procedure_type, raw_value):
    alias = key_part(raw_value)
    candidates = sorted(aliases.get((procedure_type, alias), set()))
    if len(candidates) == 1:
        return candidates[0], "resolved_procedure", "procedure_alias", "high"
    if len(candidates) > 1:
        return "", "unresolved", "ambiguous_procedure_alias", "low"
    return "", "unresolved", "missing_procedure", "low"


def resolve_rel(from_key, to_key, raw_value, method, status, confidence, table, row):
    return {
        "fromKey": from_key,
        "toKey": to_key,
        "rawValue": clean(raw_value),
        "normalizedValue": key_part(raw_value),
        "resolveMethod": method,
        "resolveStatus": status,
        "confidence": confidence,
        **source_props(table, row),
    }


def unresolved(audit_rows, table, row, source_key, raw, ref_type, status, reason):
    audit_rows.append({
        "sourceTable": table,
        "sourceRowId": row.get("_sourceRowId", ""),
        "sourceObjectKey": source_key,
        "rawValue": clean(raw),
        "normalizedValue": key_part(raw),
        "referenceType": ref_type,
        "resolveStatus": status,
        "reason": reason,
    })


def build_clean_graph_data_v1(input_dir, clean_dir, audit_dir):
    input_dir = Path(input_dir)
    clean_dir = Path(clean_dir)
    audit_dir = Path(audit_dir)
    clean_dir.mkdir(parents=True, exist_ok=True)
    audit_dir.mkdir(parents=True, exist_ok=True)

    apt_base = read_table(input_dir, "APT_BASE.csv")
    apt_rwy = read_table(input_dir, "APT_RWY.csv")
    apt_rwy_end = read_table(input_dir, "APT_RWY_END.csv")
    fix_base = read_table(input_dir, "FIX_BASE.csv")
    nav_base = read_table(input_dir, "NAV_BASE.csv")
    awy_base = read_table(input_dir, "AWY_BASE.csv")
    awy_seg = read_table(input_dir, "AWY_SEG_ALT.csv")
    dp_base = read_table(input_dir, "DP_BASE.csv")
    star_base = read_table(input_dir, "STAR_BASE.csv")
    dp_rte = read_table(input_dir, "DP_RTE.csv")
    star_rte = read_table(input_dir, "STAR_RTE.csv")
    dp_apt = read_table(input_dir, "DP_APT.csv")
    star_apt = read_table(input_dir, "STAR_APT.csv")
    pfr_base = read_table(input_dir, "PFR_BASE.csv")
    pfr_seg = read_table(input_dir, "PFR_SEG.csv")
    cdr = read_table(input_dir, "CDR.csv")

    duplicate_rows = []
    rejected_rows = []
    unresolved_rows = []
    sequence_rows = []

    duplicate_rows.extend(
        duplicate_audit("APT_BASE", "airportKey", [
            (row, airport_key(row.get("ARPT_ID"))) for row in apt_base
        ])
    )
    duplicate_rows.extend(
        duplicate_audit("NAV_BASE", "legacyNavIdTypeKey", [
            (row, join_key("POINT", "NAVAID", row.get("NAV_ID"), row.get("NAV_TYPE")))
            for row in nav_base
        ])
    )
    duplicate_rows.extend(
        duplicate_audit("AWY_BASE", "airwayKey", [
            (row, airway_key(row.get("AWY_ID"))) for row in awy_base
        ])
    )
    duplicate_rows.extend(
        duplicate_audit("DP_BASE", "legacyProcedureCodeKey", [
            (row, f"PROCEDURE:DP:{key_part(row.get('DP_COMPUTER_CODE'))}")
            for row in dp_base
        ])
    )
    airport_map = one_to_one_map(apt_base, lambda row: airport_key(row.get("ARPT_ID")))
    for row in apt_base:
        key = airport_key(row.get("ARPT_ID"))
        if key not in airport_map:
            rejected_rows.append({
                "sourceTable": "APT_BASE",
                "sourceRowId": row.get("_sourceRowId", ""),
                "key": key,
                "reason": "invalid_or_duplicate_airport_key",
            })

    airports = []
    for key, row in sorted(airport_map.items()):
        airports.append({
            "airportKey": key,
            "arptId": key_part(row.get("ARPT_ID")),
            "icaoId": key_part(row.get("ICAO_ID")),
            "siteNo": row.get("SITE_NO", ""),
            "siteTypeCode": key_part(row.get("SITE_TYPE_CODE")),
            "airportName": row.get("ARPT_NAME", ""),
            "city": row.get("CITY", ""),
            "stateCode": key_part(row.get("STATE_CODE")),
            "countryCode": key_part(row.get("COUNTRY_CODE")),
            "regionCode": key_part(row.get("REGION_CODE")),
            "lat": row.get("LAT_DECIMAL", ""),
            "lon": row.get("LONG_DECIMAL", ""),
            "elevationFt": row.get("ELEV", ""),
            "airportStatus": row.get("ARPT_STATUS", ""),
            "facilityUseCode": row.get("FACILITY_USE_CODE", ""),
            "towerTypeCode": row.get("TWR_TYPE_CODE", ""),
            "notamId": row.get("NOTAM_ID", ""),
            "notamFlag": row.get("NOTAM_FLAG", ""),
            "responsibleArtcc": row.get("RESP_ARTCC_ID", ""),
            "artccName": row.get("ARTCC_NAME", ""),
            **source_props("APT_BASE", row),
        })

    runways = []
    runway_map = {}
    for row in apt_rwy:
        key = runway_key(row.get("ARPT_ID"), row.get("RWY_ID"))
        runway_map[key] = row
        runways.append({
            "runwayKey": key,
            "arptId": key_part(row.get("ARPT_ID")),
            "rwyId": clean(row.get("RWY_ID")),
            "lengthFt": row.get("RWY_LEN", ""),
            "widthFt": row.get("RWY_WIDTH", ""),
            "surfaceTypeCode": row.get("SURFACE_TYPE_CODE", ""),
            "condition": row.get("COND", ""),
            "runwayLightCode": row.get("RWY_LGT_CODE", ""),
            "pcn": row.get("PCN", ""),
            "grossWeightSw": row.get("GROSS_WT_SW", ""),
            "grossWeightDw": row.get("GROSS_WT_DW", ""),
            "grossWeightDtw": row.get("GROSS_WT_DTW", ""),
            "grossWeightDdtw": row.get("GROSS_WT_DDTW", ""),
            **source_props("APT_RWY", row),
        })

    runway_ends = []
    runway_end_by_arpt_end = {}
    for row in apt_rwy_end:
        key = runway_end_key(row.get("ARPT_ID"), row.get("RWY_ID"), row.get("RWY_END_ID"))
        runway_end_by_arpt_end[
            (key_part(row.get("ARPT_ID")), key_part(row.get("RWY_END_ID")))
        ] = key
        runway_ends.append({
            "runwayEndKey": key,
            "arptId": key_part(row.get("ARPT_ID")),
            "rwyId": clean(row.get("RWY_ID")),
            "rwyEndId": clean(row.get("RWY_END_ID")),
            "trueAlignment": row.get("TRUE_ALIGNMENT", ""),
            "ilsType": row.get("ILS_TYPE", ""),
            "lat": row.get("LAT_DECIMAL", ""),
            "lon": row.get("LONG_DECIMAL", ""),
            "runwayEndElevationFt": row.get("RWY_END_ELEV", ""),
            "displacedThresholdLength": row.get("DISPLACED_THR_LEN", ""),
            "touchdownZoneElevationFt": row.get("TDZ_ELEV", ""),
            "vgsiCode": row.get("VGSI_CODE", ""),
            "approachLightSystemCode": row.get("APCH_LGT_SYSTEM_CODE", ""),
            "runwayEndLightsFlag": row.get("RWY_END_LGTS_FLAG", ""),
            "toraFt": row.get("TKOF_RUN_AVBL", ""),
            "todaFt": row.get("TKOF_DIST_AVBL", ""),
            "asdaFt": row.get("ACLT_STOP_DIST_AVBL", ""),
            "ldaFt": row.get("LNDG_DIST_AVBL", ""),
            **source_props("APT_RWY_END", row),
        })

    rel_airport_has_runway = [
        base_rel(airport_key(row.get("ARPT_ID")), runway_key(row.get("ARPT_ID"), row.get("RWY_ID")), "APT_RWY", row)
        for row in apt_rwy
        if airport_key(row.get("ARPT_ID")) in airport_map
    ]
    rel_runway_has_end = [
        base_rel(
            runway_key(row.get("ARPT_ID"), row.get("RWY_ID")),
            runway_end_key(row.get("ARPT_ID"), row.get("RWY_ID"), row.get("RWY_END_ID")),
            "APT_RWY_END",
            row,
        )
        for row in apt_rwy_end
        if runway_key(row.get("ARPT_ID"), row.get("RWY_ID")) in runway_map
    ]

    route_points = []
    for row in fix_base:
        route_points.append({
            "pointKey": fix_key(row.get("FIX_ID"), row.get("ICAO_REGION_CODE")),
            "pointType": "FIX",
            "pointId": key_part(row.get("FIX_ID")),
            "name": key_part(row.get("FIX_ID")),
            "icaoRegionCode": key_part(row.get("ICAO_REGION_CODE")),
            "stateCode": key_part(row.get("STATE_CODE")),
            "countryCode": key_part(row.get("COUNTRY_CODE")),
            "lat": row.get("LAT_DECIMAL", ""),
            "lon": row.get("LONG_DECIMAL", ""),
            "fixUseCode": row.get("FIX_USE_CODE", ""),
            "artccIdHigh": row.get("ARTCC_ID_HIGH", ""),
            "artccIdLow": row.get("ARTCC_ID_LOW", ""),
            "minimumReceptionAltitudeFt": row.get("MIN_RECEP_ALT", ""),
            "compulsory": row.get("COMPULSORY", ""),
            "charts": row.get("CHARTS", ""),
            **source_props("FIX_BASE", row),
        })
    for row in nav_base:
        route_points.append({
            "pointKey": navaid_key(row),
            "pointType": "NAVAID",
            "pointId": key_part(row.get("NAV_ID")),
            "name": row.get("NAME", ""),
            "navId": key_part(row.get("NAV_ID")),
            "navType": key_part(row.get("NAV_TYPE")),
            "navStatus": row.get("NAV_STATUS", ""),
            "city": row.get("CITY", ""),
            "stateCode": key_part(row.get("STATE_CODE")),
            "countryCode": key_part(row.get("COUNTRY_CODE")),
            "regionCode": key_part(row.get("REGION_CODE")),
            "lat": row.get("LAT_DECIMAL", ""),
            "lon": row.get("LONG_DECIMAL", ""),
            "elevationFt": row.get("ELEV", ""),
            "freq": row.get("FREQ", ""),
            "chan": row.get("CHAN", ""),
            "nasUseFlag": row.get("NAS_USE_FLAG", ""),
            "publicUseFlag": row.get("PUBLIC_USE_FLAG", ""),
            "operatingHours": row.get("OPER_HOURS", ""),
            "highAltArtccId": row.get("HIGH_ALT_ARTCC_ID", ""),
            "lowAltArtccId": row.get("LOW_ALT_ARTCC_ID", ""),
            "notamId": row.get("NOTAM_ID", ""),
            "restrictionFlag": row.get("RESTRICTION_FLAG", ""),
            **source_props("NAV_BASE", row),
        })

    indexes = build_route_point_indexes(route_points)
    boundary_rows = {}
    for row in awy_seg:
        raw = row.get("FROM_POINT")
        raw_type = row.get("FROM_PT_TYPE")
        resolved_key, status, _, _ = resolve_route_point(raw, raw_type, row, indexes)
        if not resolved_key and is_boundary_point(raw, row):
            key = boundary_key(raw)
            boundary_rows.setdefault(key, row)
    for index, (key, row) in enumerate(sorted(boundary_rows.items()), start=1):
        raw_name = row.get("FROM_POINT")
        country = "CANADA" if "CANAD" in clean_id(raw_name) else "MEXICO"
        route_points.append({
            "pointKey": key,
            "pointType": "BOUNDARY",
            "pointId": key.rsplit(":", 1)[1],
            "name": key.rsplit(":", 1)[1],
            "rawName": raw_name,
            "normalizedName": key.rsplit(":", 1)[1],
            "boundaryType": "international_boundary",
            "adjacentCountry": country,
            "boundaryIndex": index,
            **source_props("AWY_SEG_ALT", row),
        })
    indexes = build_route_point_indexes(route_points)

    reference_procedure_lookup = {}
    for row in dp_base:
        key = procedure_key("DP", row.get("DP_COMPUTER_CODE"), row)
        reference_procedure_lookup[
            (
                "DP", key_part(row.get("DP_COMPUTER_CODE")),
                key_part(row.get("DP_NAME")), key_part(row.get("ARTCC")),
            )
        ] = key
    for row in star_base:
        key = procedure_key("STAR", row.get("STAR_COMPUTER_CODE"), row)
        reference_procedure_lookup[
            (
                "STAR", key_part(row.get("STAR_COMPUTER_CODE")),
                "", key_part(row.get("ARTCC")),
            )
        ] = key

    navaid_groups = defaultdict(list)
    for row in nav_base:
        navaid_groups[(key_part(row.get("NAV_ID")), key_part(row.get("NAV_TYPE")))].append(row)

    navaid_reference_sources = []
    for table, rows, raw_col, type_col in (
        ("AWY_SEG_ALT", awy_seg, "FROM_POINT", "FROM_PT_TYPE"),
        ("DP_RTE", dp_rte, "POINT", "POINT_TYPE"),
        ("STAR_RTE", star_rte, "POINT", "POINT_TYPE"),
    ):
        for row in rows:
            if is_navaid_reference(row.get(type_col)):
                navaid_reference_sources.append((table, row, raw_col, type_col))
    for row in pfr_seg:
        if key_part(row.get("SEG_TYPE")) == "NAVAID":
            navaid_reference_sources.append(("PFR_SEG", row, "SEG_VALUE", "NAV_TYPE"))

    navaid_reference_counts = {
        "AWY_SEG_ALT": Counter(),
        "DP_RTE": Counter(),
        "STAR_RTE": Counter(),
        "PFR_SEG": Counter(),
    }
    for table, row, raw_col, type_col in navaid_reference_sources:
        navaid_reference_counts[table][
            (key_part(row.get(raw_col)), key_part(row.get(type_col)))
        ] += 1

    navaid_group_analysis = []
    for (nav_id, nav_type), rows in sorted(navaid_groups.items()):
        navaid_group_analysis.append({
            "navId": nav_id,
            "navType": nav_type,
            "groupSize": len(rows),
            "sourceRowIds": "|".join(row["_sourceRowId"] for row in rows),
            "distinctNameCount": len(sorted_values(row.get("NAME") for row in rows)),
            "nameList": pipe(row.get("NAME") for row in rows),
            "distinctCityCount": len(sorted_values(row.get("CITY") for row in rows)),
            "cityList": pipe(row.get("CITY") for row in rows),
            "distinctStateCount": len(sorted_values(row.get("STATE_CODE") for row in rows)),
            "stateList": pipe(row.get("STATE_CODE") for row in rows),
            "distinctCountryCount": len(sorted_values(row.get("COUNTRY_CODE") for row in rows)),
            "countryList": pipe(row.get("COUNTRY_CODE") for row in rows),
            "distinctFreqCount": len(sorted_values(row.get("FREQ") for row in rows)),
            "freqList": pipe(row.get("FREQ") for row in rows),
            "distinctChanCount": len(sorted_values(row.get("CHAN") for row in rows)),
            "chanList": pipe(row.get("CHAN") for row in rows),
            "latLonList": pipe(lat_lon(row) for row in rows),
            "navStatusList": pipe(row.get("NAV_STATUS") for row in rows),
            "nasUseFlagList": pipe(row.get("NAS_USE_FLAG") for row in rows),
            "publicUseFlagList": pipe(row.get("PUBLIC_USE_FLAG") for row in rows),
            "appearsInAwySegCount": navaid_reference_counts["AWY_SEG_ALT"][(nav_id, nav_type)],
            "appearsInDpRteCount": navaid_reference_counts["DP_RTE"][(nav_id, nav_type)],
            "appearsInStarRteCount": navaid_reference_counts["STAR_RTE"][(nav_id, nav_type)],
            "appearsInPfrSegCount": navaid_reference_counts["PFR_SEG"][(nav_id, nav_type)],
            "preliminaryPattern": navaid_group_pattern(rows),
        })
    navaid_duplicate_groups_for_review = []
    for row in navaid_group_analysis:
        if int(row["groupSize"]) <= 1:
            continue
        referenced = any(
            int(row[field]) > 0
            for field in (
                "appearsInAwySegCount", "appearsInDpRteCount",
                "appearsInStarRteCount", "appearsInPfrSegCount",
            )
        )
        navaid_duplicate_groups_for_review.append({
            **row,
            "nameConflict": str(int(row["distinctNameCount"]) > 1).lower(),
            "cityConflict": str(int(row["distinctCityCount"]) > 1).lower(),
            "stateConflict": str(int(row["distinctStateCount"]) > 1).lower(),
            "countryConflict": str(int(row["distinctCountryCount"]) > 1).lower(),
            "freqConflict": str(int(row["distinctFreqCount"]) > 1).lower(),
            "coordConflict": str(len(row["latLonList"].split("|")) > 1).lower(),
            "referencedInAnyRouteData": str(referenced).lower(),
        })

    navaid_group_detail = []
    navaid_source_rows_by_point = {}
    for row in nav_base:
        point_key = navaid_key(row)
        navaid_source_rows_by_point[point_key] = row.get("_sourceRowId", "")
        navaid_group_detail.append({
            "navId": key_part(row.get("NAV_ID")),
            "navType": key_part(row.get("NAV_TYPE")),
            "sourceRowId": row.get("_sourceRowId", ""),
            "name": row.get("NAME", ""),
            "city": row.get("CITY", ""),
            "stateCode": row.get("STATE_CODE", ""),
            "countryCode": row.get("COUNTRY_CODE", ""),
            "regionCode": row.get("REGION_CODE", ""),
            "lat": row.get("LAT_DECIMAL", ""),
            "lon": row.get("LONG_DECIMAL", ""),
            "freq": row.get("FREQ", ""),
            "chan": row.get("CHAN", ""),
            "navStatus": row.get("NAV_STATUS", ""),
            "nasUseFlag": row.get("NAS_USE_FLAG", ""),
            "publicUseFlag": row.get("PUBLIC_USE_FLAG", ""),
            "highAltArtccId": row.get("HIGH_ALT_ARTCC_ID", ""),
            "lowAltArtccId": row.get("LOW_ALT_ARTCC_ID", ""),
            "legacyNavIdTypeKey": join_key("POINT", "NAVAID", row.get("NAV_ID"), row.get("NAV_TYPE")),
            "currentPointKey": point_key,
        })

    navaid_reference_ambiguity = []
    for table, row, raw_col, type_col in navaid_reference_sources:
        raw_value = key_part(row.get(raw_col))
        raw_nav_type = key_part(row.get(type_col))
        candidates = sorted(indexes["navaids_by_id_type"].get((raw_value, raw_nav_type), []))
        resolved_key, status, _, _ = resolve_route_point(
            row.get(raw_col), row.get(type_col), row, indexes
        )
        if len(candidates) > 1 and not resolved_key:
            reason = "ambiguous_navaid_reference"
        elif len(candidates) > 1:
            reason = "resolved_by_context"
        elif len(candidates) == 1:
            reason = "single_candidate"
        else:
            reason = "no_candidate"
        navaid_reference_ambiguity.append({
            "sourceTable": table,
            "sourceRowId": row.get("_sourceRowId", ""),
            "sourceObjectKey": source_object_key_for_reference(
                table, row, reference_procedure_lookup
            ),
            "rawValue": row.get(raw_col, ""),
            "rawNavType": row.get(type_col, ""),
            "contextStateCode": row.get("STATE_CODE", ""),
            "contextCountryCode": row.get("COUNTRY_CODE", ""),
            "contextIcaoRegionCode": row.get("ICAO_REGION_CODE", ""),
            "candidateCountByNavIdType": len(candidates),
            "candidatePointKeys": "|".join(candidates),
            "candidateSourceRowIds": "|".join(
                navaid_source_rows_by_point.get(candidate, "")
                for candidate in candidates
            ),
            "currentResolvedPointKey": resolved_key,
            "currentResolveStatus": status,
            "ambiguityReason": reason,
        })
    navaid_ambiguous_references_for_review = [
        row for row in navaid_reference_ambiguity
        if row["ambiguityReason"] == "ambiguous_navaid_reference"
    ]

    awy_by_id = defaultdict(list)
    for row in awy_base:
        awy_by_id[key_part(row.get("AWY_ID"))].append(row)
    airways = []
    for awy_id, rows in sorted(awy_by_id.items()):
        first = rows[0]
        airways.append({
            "airwayKey": airway_key(awy_id),
            "awyId": awy_id,
            "awyDesignation": first.get("AWY_DESIGNATION", ""),
            "regulatory": first.get("REGULATORY", ""),
            "remark": first.get("REMARK", ""),
            "airwayString": first.get("AIRWAY_STRING", ""),
            "updateDate": first.get("UPDATE_DATE", ""),
            "sourceCycle": SOURCE_CYCLE,
            "sourceTable": "AWY_BASE",
            "sourceRowId": "|".join(row["_sourceRowId"] for row in rows),
        })

    airway_paths = []
    rel_airway_has_path = []
    for row in awy_base:
        path_key = airway_path_key(row.get("AWY_ID"), row.get("AWY_LOCATION"))
        airway_paths.append({
            "airwayPathKey": path_key,
            "airwayKey": airway_key(row.get("AWY_ID")),
            "awyId": key_part(row.get("AWY_ID")),
            "awyLocation": key_part(row.get("AWY_LOCATION")),
            "awyDesignation": row.get("AWY_DESIGNATION", ""),
            "airwayString": row.get("AIRWAY_STRING", ""),
            **source_props("AWY_BASE", row),
        })
        rel_airway_has_path.append(
            base_rel(airway_key(row.get("AWY_ID")), path_key, "AWY_BASE", row)
        )

    airway_occurrences = []
    rel_airway_path_has_occurrence = []
    rel_airway_occurrence_resolves_to = []
    by_airway_path = defaultdict(list)
    for row in awy_seg:
        path_key = airway_path_key(row.get("AWY_ID"), row.get("AWY_LOCATION"))
        occ_key = airway_occurrence_key(row.get("AWY_ID"), row.get("AWY_LOCATION"), row.get("POINT_SEQ"))
        resolved_key, status, method, confidence = resolve_route_point(
            row.get("FROM_POINT"), row.get("FROM_PT_TYPE"), row, indexes
        )
        if not resolved_key and is_boundary_point(row.get("FROM_POINT"), row):
            resolved_key = boundary_key(row.get("FROM_POINT"))
            status, method, confidence = "resolved_boundary", "boundary_pattern", "medium"
        if not resolved_key:
            unresolved(unresolved_rows, "AWY_SEG_ALT", row, occ_key, row.get("FROM_POINT"), row.get("FROM_PT_TYPE"), status, method)
        occurrence = {
            "airwayOccurrenceKey": occ_key,
            "airwayPathKey": path_key,
            "awyId": key_part(row.get("AWY_ID")),
            "awyLocation": key_part(row.get("AWY_LOCATION")),
            "pointSeq": key_part(row.get("POINT_SEQ")),
            "rawFromPoint": row.get("FROM_POINT", ""),
            "rawFromPointType": row.get("FROM_PT_TYPE", ""),
            "rawToPoint": row.get("TO_POINT", ""),
            "rawNextMeaPoint": row.get("NEXT_MEA_PT", ""),
            "resolvedPointKey": resolved_key,
            "resolveStatus": status,
            "_row": row,
            **source_props("AWY_SEG_ALT", row),
        }
        airway_occurrences.append(occurrence)
        by_airway_path[path_key].append(occurrence)
        rel_airway_path_has_occurrence.append(
            base_rel(path_key, occ_key, "AWY_SEG_ALT", row)
        )
        if resolved_key:
            rel_airway_occurrence_resolves_to.append(
                resolve_rel(occ_key, resolved_key, row.get("FROM_POINT"), method, status, confidence, "AWY_SEG_ALT", row)
            )

    rel_next_on_airway = []
    for path_key, items in by_airway_path.items():
        ordered = sorted(items, key=lambda item: numeric_seq(item["pointSeq"]))
        if ordered:
            ordered[0]["occurrenceRole"] = "START"
            ordered[-1]["occurrenceRole"] = "END"
            for item in ordered[1:-1]:
                item["occurrenceRole"] = "INTERMEDIATE"
        for current, nxt in zip(ordered, ordered[1:]):
            row = current["_row"]
            rel_next_on_airway.append({
                "fromKey": current["airwayOccurrenceKey"],
                "toKey": nxt["airwayOccurrenceKey"],
                "magCourse": row.get("MAG_COURSE", ""),
                "oppositeMagCourse": row.get("OPP_MAG_COURSE", ""),
                "distanceNm": row.get("MAG_COURSE_DIST", ""),
                "minEnrouteAltFt": row.get("MIN_ENROUTE_ALT", ""),
                "minEnrouteAltOppositeFt": row.get("MIN_ENROUTE_ALT_OPPOSITE", ""),
                "gpsMinEnrouteAltFt": row.get("GPS_MIN_ENROUTE_ALT", ""),
                "minObstacleClearanceAltFt": row.get("MIN_OBSTN_CLNC_ALT", ""),
                "minCrossingAltFt": row.get("MIN_CROSS_ALT", ""),
                "minReceptionAltFt": row.get("MIN_RECEP_ALT", ""),
                "maxAuthorizedAltFt": row.get("MAX_AUTH_ALT", ""),
                "requiredNavPerformance": row.get("REQD_NAV_PERFORMANCE", ""),
                "gapFlag": row.get("AWY_SEG_GAP_FLAG", ""),
                "signalGapFlag": row.get("SIGNAL_GAP_FLAG", ""),
                "dogleg": row.get("DOGLEG", ""),
                "artcc": row.get("ARTCC", ""),
                "stateCode": row.get("STATE_CODE", ""),
                "countryCode": row.get("COUNTRY_CODE", ""),
                "icaoRegionCode": row.get("ICAO_REGION_CODE", ""),
                **source_props("AWY_SEG_ALT", row),
            })
        sequence_rows.extend(
            audit_path_sequence(
                [item["_row"] for item in items],
                "AWY_SEG_ALT",
                path_key,
                "FROM_POINT",
                "TO_POINT",
            )
        )

    for item in airway_occurrences:
        item.pop("_row", None)

    procedure_base_rows = []
    procedure_lookup = {}
    for row in dp_base:
        key = procedure_key("DP", row.get("DP_COMPUTER_CODE"), row)
        procedure_lookup[("DP", key_part(row.get("DP_COMPUTER_CODE")), key_part(row.get("DP_NAME")), key_part(row.get("ARTCC")))] = key
        procedure_base_rows.append(("DP", key, row))
    for row in star_base:
        key = procedure_key("STAR", row.get("STAR_COMPUTER_CODE"), row)
        procedure_lookup[("STAR", key_part(row.get("STAR_COMPUTER_CODE")), "", key_part(row.get("ARTCC")))] = key
        procedure_base_rows.append(("STAR", key, row))

    procedures = []
    procedure_aliases = defaultdict(set)
    for proc_type, key, row in procedure_base_rows:
        code = row.get("DP_COMPUTER_CODE", "") or row.get("STAR_COMPUTER_CODE", "")
        procedure_name = row.get("DP_NAME", "") or row.get("ARRIVAL_NAME", "")
        add_procedure_alias(procedure_aliases, proc_type, code, key)
        for part in key_part(code).split("."):
            add_procedure_alias(procedure_aliases, proc_type, part, key)
        amend = amendment_number(row.get("AMENDMENT_NO"))
        if amend:
            add_procedure_alias(procedure_aliases, proc_type, f"{procedure_name}{amend}", key)
        procedures.append({
            "procedureKey": key,
            "procedureType": proc_type,
            "procedureName": row.get("DP_NAME", "") or row.get("ARRIVAL_NAME", ""),
            "computerCode": key_part(row.get("DP_COMPUTER_CODE", "") or row.get("STAR_COMPUTER_CODE", "")),
            "amendmentNo": row.get("AMENDMENT_NO", ""),
            "artcc": row.get("ARTCC", ""),
            "effectiveDate": row.get("DP_AMEND_EFF_DATE", "") or row.get("STAR_AMEND_EFF_DATE", ""),
            "rnavFlag": row.get("RNAV_FLAG", ""),
            "servedAirportRaw": row.get("SERVED_ARPT", ""),
            "graphicalType": row.get("GRAPHICAL_DP_TYPE", ""),
            **source_props(row["_sourceTable"], row),
        })

    def procedure_key_for_rte(proc_type, row):
        return procedure_key_for_rte_row(proc_type, row, procedure_lookup)

    procedure_paths_by_key = {}
    procedure_path_source_rows = defaultdict(list)
    procedure_occurrences = []
    rel_procedure_path_has_occurrence = []
    rel_procedure_occurrence_resolves_to = []
    by_procedure_path = defaultdict(list)

    for proc_type, rows, table in (("DP", dp_rte, "DP_RTE"), ("STAR", star_rte, "STAR_RTE")):
        for row in rows:
            proc_key = procedure_key_for_rte(proc_type, row)
            path_key = procedure_path_key(proc_key, row)
            procedure_path_source_rows[path_key].append(row.get("_sourceRowId", ""))
            procedure_paths_by_key[path_key] = {
                "procedurePathKey": path_key,
                "procedureKey": proc_key,
                "procedureType": proc_type,
                "routePortionType": row.get("ROUTE_PORTION_TYPE", ""),
                "routeName": row.get("ROUTE_NAME", ""),
                "bodySeq": row.get("BODY_SEQ", ""),
                "transitionComputerCode": row.get("TRANSITION_COMPUTER_CODE", ""),
                "sourceAggregation": "true",
                **source_props(table, row),
            }
            occ_key = procedure_occurrence_key(path_key, row.get("POINT_SEQ"))
            resolved_key, status, method, confidence = resolve_route_point(
                row.get("POINT"), row.get("POINT_TYPE"), row, indexes
            )
            if not resolved_key:
                unresolved(unresolved_rows, table, row, occ_key, row.get("POINT"), row.get("POINT_TYPE"), status, method)
            occurrence = {
                "procedureOccurrenceKey": occ_key,
                "procedurePathKey": path_key,
                "procedureKey": proc_key,
                "procedureType": proc_type,
                "pointSeq": key_part(row.get("POINT_SEQ")),
                "rawPoint": row.get("POINT", ""),
                "rawPointType": row.get("POINT_TYPE", ""),
                "nextPointRaw": row.get("NEXT_POINT", ""),
                "arptRwyAssoc": row.get("ARPT_RWY_ASSOC", ""),
                "resolvedPointKey": resolved_key,
                "resolveStatus": status,
                "_row": row,
                "_table": table,
                **source_props(table, row),
            }
            procedure_occurrences.append(occurrence)
            by_procedure_path[path_key].append(occurrence)
            rel_procedure_path_has_occurrence.append(
                base_rel(path_key, occ_key, table, row)
            )
            if resolved_key:
                rel_procedure_occurrence_resolves_to.append(
                    resolve_rel(occ_key, resolved_key, row.get("POINT"), method, status, confidence, table, row)
                )

    procedure_paths = []
    for path_key, path in sorted(procedure_paths_by_key.items()):
        source_row_ids = procedure_path_source_rows[path_key]
        path["sourceRowIds"] = "|".join(source_row_ids)
        path["sourceRowCount"] = len(source_row_ids)
        procedure_paths.append(path)
    rel_procedure_has_path = [
        base_rel(row["procedureKey"], row["procedurePathKey"], row["sourceTable"], row)
        for row in procedure_paths
    ]
    rel_next_on_procedure = []
    for path_key, items in by_procedure_path.items():
        ordered = sorted(items, key=lambda item: numeric_seq(item["pointSeq"]))
        for current, nxt in zip(ordered, ordered[1:]):
            row = current["_row"]
            rel_next_on_procedure.append({
                "fromKey": current["procedureOccurrenceKey"],
                "toKey": nxt["procedureOccurrenceKey"],
                "sourceNextPointRaw": row.get("NEXT_POINT", ""),
                "sequenceCheckStatus": "ordered_by_point_seq",
                "directionStatus": "source_sequence",
                **source_props(current["_table"], row),
            })
        if items:
            sequence_rows.extend(
                audit_path_sequence(
                    [item["_row"] for item in items],
                    items[0]["_table"],
                    path_key,
                    "POINT",
                    "NEXT_POINT",
                )
            )
    for item in procedure_occurrences:
        item.pop("_row", None)
        item.pop("_table", None)

    rel_procedure_serves_airport = []
    rel_procedure_path_associated_with_runway_end = []
    for proc_type, rows, table, code_field in (
        ("DP", dp_apt, "DP_APT", "DP_COMPUTER_CODE"),
        ("STAR", star_apt, "STAR_APT", "STAR_COMPUTER_CODE"),
    ):
        for row in rows:
            if proc_type == "DP":
                proc_key = f"PROCEDURE:DP:{key_part(row.get(code_field))}"
            else:
                proc_key = f"PROCEDURE:STAR:{key_part(row.get(code_field))}"
            arpt_key = airport_key(row.get("ARPT_ID"))
            if arpt_key in airport_map:
                rel_procedure_serves_airport.append(
                    base_rel(proc_key, arpt_key, table, row)
                )
            route_name = row.get("BODY_NAME")
            path_matches = [
                path for path in procedure_paths
                if path["procedureKey"] == proc_key
                and key_part(path["bodySeq"]) == key_part(row.get("BODY_SEQ"))
                and key_part(path["routeName"]) == key_part(route_name)
            ]
            runway_end = runway_end_by_arpt_end.get(
                (key_part(row.get("ARPT_ID")), key_part(row.get("RWY_END_ID")))
            )
            if runway_end:
                for path in path_matches:
                    rel_procedure_path_associated_with_runway_end.append(
                        base_rel(path["procedurePathKey"], runway_end, table, row)
                    )

    route_templates = []
    template_paths = []
    template_tokens = []
    rel_template_origin_ref = []
    rel_template_destination_ref = []
    rel_template_has_path = []
    rel_template_path_has_occurrence = []
    rel_next_template_token = []
    rel_template_token_references = []

    pfr_base_by_key = {pfr_template_key(row): row for row in pfr_base}
    token_by_template = defaultdict(list)
    for row in pfr_seg:
        token_by_template[pfr_template_key(row)].append(row)

    airway_keys = {row["airwayKey"] for row in airways}
    def resolve_template_endpoint(raw, row):
        arpt_key = airport_key(raw)
        if arpt_key in airport_map:
            return arpt_key, "Airport", "airport_id", "resolved", "high"
        point_key, status, method, confidence = resolve_route_point(raw, "", row, indexes)
        if point_key:
            return point_key, "RoutePoint", method, status, confidence
        return "", "", method, status, confidence

    for row in pfr_base:
        key = pfr_template_key(row)
        path_key = template_path_key(key)
        route_templates.append({
            "templateKey": key,
            "templateType": "PFR",
            "originRaw": row.get("ORIGIN_ID", ""),
            "destinationRaw": row.get("DSTN_ID", ""),
            "originCity": row.get("ORIGIN_CITY", ""),
            "destinationCity": row.get("DSTN_CITY", ""),
            "pfrTypeCode": row.get("PFR_TYPE_CODE", ""),
            "routeNo": row.get("ROUTE_NO", ""),
            "specialAreaDesc": row.get("SPECIAL_AREA_DESCRIP", ""),
            "altitudeDescription": row.get("ALT_DESCRIP", ""),
            "aircraft": row.get("AIRCRAFT", ""),
            "hours": row.get("HOURS", ""),
            "directionDescription": row.get("ROUTE_DIR_DESCRIP", ""),
            "designator": row.get("DESIGNATOR", ""),
            "narType": row.get("NAR_TYPE", ""),
            "inlandFacilityFix": row.get("INLAND_FAC_FIX", ""),
            "coastalFix": row.get("COASTAL_FIX", ""),
            "destinationDesc": row.get("DESTINATION", ""),
            "routeString": row.get("ROUTE_STRING", ""),
            "parseStatus": "structured_segments",
            **source_props("PFR_BASE", row),
        })
        template_paths.append({
            "templatePathKey": path_key,
            "templateKey": key,
            "templateType": "PFR",
            "routeString": row.get("ROUTE_STRING", ""),
            "sourceCycle": SOURCE_CYCLE,
            "sourceTable": "PFR_BASE/PFR_SEG",
            "sourceRowId": row.get("_sourceRowId", ""),
        })
        rel_template_has_path.append(
            base_rel(key, path_key, "PFR_BASE", row)
        )
        for raw, rel_rows, rel_type in (
            (row.get("ORIGIN_ID"), rel_template_origin_ref, "origin"),
            (row.get("DSTN_ID"), rel_template_destination_ref, "destination"),
        ):
            target, _, method, status, confidence = resolve_template_endpoint(raw, row)
            if target:
                rel_rows.append(
                    resolve_rel(key, target, raw, method, status, confidence, "PFR_BASE", row)
                )
            else:
                unresolved(unresolved_rows, "PFR_BASE", row, key, raw, rel_type, status, method)

    for row in cdr:
        route_templates.append({
            "templateKey": cdr_template_key(row),
            "templateType": "CDR",
            "originRaw": row.get("ORIG", ""),
            "destinationRaw": row.get("DEST", ""),
            "codedRouteCode": row.get("RCODE", ""),
            "departureFixRaw": row.get("DEPFIX", ""),
            "routeString": row.get("ROUTE STRING", ""),
            "departureCenter": row.get("DCNTR", ""),
            "arrivalCenter": row.get("ACNTR", ""),
            "throughCenters": row.get("TCNTRS", ""),
            "coordinationRequired": row.get("COORDREQ", ""),
            "play": row.get("PLAY", ""),
            "navigationEquipment": row.get("NAVEQP", ""),
            "lengthNm": row.get("LENGTH", ""),
            "parseStatus": "raw_only",
            **source_props("CDR", row),
        })

    for tmpl_key, rows in sorted(token_by_template.items()):
        if tmpl_key not in pfr_base_by_key:
            for row in rows:
                rejected_rows.append({
                    "sourceTable": "PFR_SEG",
                    "sourceRowId": row.get("_sourceRowId", ""),
                    "key": tmpl_key,
                    "reason": "missing_pfr_base",
                })
            continue
        path_key = template_path_key(tmpl_key)
        ordered = sorted(rows, key=lambda row: numeric_seq(row.get("SEGMENT_SEQ")))
        previous_key = ""
        for row in ordered:
            token_key = template_token_key(tmpl_key, row.get("SEGMENT_SEQ"))
            seg_type = key_part(row.get("SEG_TYPE"))
            raw = row.get("SEG_VALUE")
            ref_key = ""
            ref_type = ""
            status = "unresolved"
            method = "unsupported_segment_type"
            confidence = "low"
            if seg_type == "FIX":
                ref_key, status, method, confidence = resolve_route_point(raw, "FIX", row, indexes)
                ref_type = "RoutePoint" if ref_key else ""
            elif seg_type == "NAVAID":
                ref_key, status, method, confidence = resolve_route_point(raw, row.get("NAV_TYPE"), row, indexes)
                ref_type = "RoutePoint" if ref_key else ""
            elif seg_type == "AIRWAY":
                candidate = airway_key(raw)
                if candidate in airway_keys:
                    ref_key, ref_type, status, method, confidence = candidate, "Airway", "resolved_airway", "airway_id", "high"
                else:
                    status, method = "unresolved", "missing_airway"
            elif seg_type in {"DP", "STAR"}:
                ref_key, status, method, confidence = resolve_procedure_alias(
                    procedure_aliases, seg_type, raw
                )
                ref_type = "Procedure" if ref_key else ""
            elif seg_type in {"RADIAL", "FRD"}:
                status, method = "unsupported", f"unsupported_{seg_type.lower()}"
            if not ref_key and status != "unsupported":
                unresolved(unresolved_rows, "PFR_SEG", row, token_key, raw, seg_type, status, method)
            template_tokens.append({
                "templateTokenKey": token_key,
                "templatePathKey": path_key,
                "templateKey": tmpl_key,
                "segmentSeq": key_part(row.get("SEGMENT_SEQ")),
                "segValueRaw": raw,
                "segType": seg_type,
                "navType": row.get("NAV_TYPE", ""),
                "nextSegRaw": row.get("NEXT_SEG", ""),
                "resolvedRefKey": ref_key,
                "resolvedRefType": ref_type,
                "resolveStatus": status,
                **source_props("PFR_SEG", row),
            })
            rel_template_path_has_occurrence.append(
                base_rel(path_key, token_key, "PFR_SEG", row)
            )
            if previous_key:
                rel_next_template_token.append(
                    base_rel(previous_key, token_key, "PFR_SEG", row)
                )
            previous_key = token_key
            if ref_key:
                rel_template_token_references.append({
                    "fromKey": token_key,
                    "toKey": ref_key,
                    "refType": ref_type,
                    "rawValue": raw,
                    "normalizedValue": key_part(raw),
                    "resolveMethod": method,
                    "resolveStatus": status,
                    "confidence": confidence,
                    **source_props("PFR_SEG", row),
                })

    old_projection_files = {
        "clean_edges_bidirectional.csv",
        "clean_edges_original.csv",
        "clean_edge_sources.csv",
        "clean_routes.csv",
    }
    for name in old_projection_files:
        path = clean_dir / name
        if path.exists():
            path.unlink()

    write_csv(clean_dir / "clean_airports.csv", AIRPORT_COLUMNS, airports)
    write_csv(clean_dir / "clean_runways.csv", RUNWAY_COLUMNS, runways)
    write_csv(clean_dir / "clean_runway_ends.csv", RUNWAY_END_COLUMNS, runway_ends)
    write_csv(clean_dir / "clean_route_points.csv", ROUTE_POINT_COLUMNS, route_points)
    write_csv(clean_dir / "rel_airport_has_runway.csv", REL_COLUMNS, rel_airport_has_runway)
    write_csv(clean_dir / "rel_runway_has_runway_end.csv", REL_COLUMNS, rel_runway_has_end)
    write_csv(clean_dir / "clean_airways.csv", AIRWAY_COLUMNS, airways)
    write_csv(clean_dir / "clean_airway_paths.csv", AIRWAY_PATH_COLUMNS, airway_paths)
    write_csv(clean_dir / "clean_airway_occurrences.csv", AIRWAY_OCCURRENCE_COLUMNS, airway_occurrences)
    write_csv(clean_dir / "rel_airway_has_path.csv", REL_COLUMNS, rel_airway_has_path)
    write_csv(clean_dir / "rel_airway_path_has_occurrence.csv", REL_COLUMNS, rel_airway_path_has_occurrence)
    write_csv(clean_dir / "rel_airway_occurrence_resolves_to.csv", RESOLVE_REL_COLUMNS, rel_airway_occurrence_resolves_to)
    write_csv(clean_dir / "rel_next_on_airway.csv", NEXT_AIRWAY_COLUMNS, rel_next_on_airway)
    write_csv(clean_dir / "clean_procedures.csv", PROCEDURE_COLUMNS, procedures)
    write_csv(clean_dir / "clean_procedure_paths.csv", PROCEDURE_PATH_COLUMNS, procedure_paths)
    write_csv(clean_dir / "clean_procedure_occurrences.csv", PROCEDURE_OCCURRENCE_COLUMNS, procedure_occurrences)
    write_csv(clean_dir / "rel_procedure_has_path.csv", REL_COLUMNS, rel_procedure_has_path)
    write_csv(clean_dir / "rel_procedure_serves_airport.csv", REL_COLUMNS, rel_procedure_serves_airport)
    write_csv(clean_dir / "rel_procedure_path_has_occurrence.csv", REL_COLUMNS, rel_procedure_path_has_occurrence)
    write_csv(clean_dir / "rel_procedure_occurrence_resolves_to.csv", RESOLVE_REL_COLUMNS, rel_procedure_occurrence_resolves_to)
    write_csv(clean_dir / "rel_next_on_procedure.csv", NEXT_PROCEDURE_COLUMNS, rel_next_on_procedure)
    write_csv(clean_dir / "rel_procedure_path_associated_with_runway_end.csv", REL_COLUMNS, rel_procedure_path_associated_with_runway_end)
    write_csv(clean_dir / "clean_route_templates.csv", TEMPLATE_COLUMNS, route_templates)
    write_csv(clean_dir / "clean_template_paths.csv", TEMPLATE_PATH_COLUMNS, template_paths)
    write_csv(clean_dir / "clean_template_tokens.csv", TEMPLATE_TOKEN_COLUMNS, template_tokens)
    write_csv(clean_dir / "rel_template_origin_ref.csv", RESOLVE_REL_COLUMNS, rel_template_origin_ref)
    write_csv(clean_dir / "rel_template_destination_ref.csv", RESOLVE_REL_COLUMNS, rel_template_destination_ref)
    write_csv(clean_dir / "rel_template_has_path.csv", REL_COLUMNS, rel_template_has_path)
    write_csv(clean_dir / "rel_template_path_has_occurrence.csv", REL_COLUMNS, rel_template_path_has_occurrence)
    write_csv(clean_dir / "rel_next_template_token.csv", REL_COLUMNS, rel_next_template_token)
    write_csv(clean_dir / "rel_template_token_references.csv", TEMPLATE_REF_COLUMNS, rel_template_token_references)

    write_csv(audit_dir / "audit_duplicate_keys.csv", AUDIT_DUPLICATE_COLUMNS, duplicate_rows)
    write_csv(audit_dir / "audit_unresolved_references.csv", AUDIT_UNRESOLVED_COLUMNS, unresolved_rows)
    write_csv(audit_dir / "audit_rejected_rows.csv", AUDIT_REJECTED_COLUMNS, rejected_rows)
    write_csv(audit_dir / "audit_sequence_issues.csv", AUDIT_SEQUENCE_COLUMNS, sequence_rows)
    write_csv(
        audit_dir / "navaid_entity_group_analysis.csv",
        NAVAID_GROUP_ANALYSIS_COLUMNS,
        navaid_group_analysis,
    )
    write_csv(
        audit_dir / "navaid_entity_group_detail.csv",
        NAVAID_GROUP_DETAIL_COLUMNS,
        navaid_group_detail,
    )
    write_csv(
        audit_dir / "navaid_reference_ambiguity_analysis.csv",
        NAVAID_REFERENCE_AMBIGUITY_COLUMNS,
        navaid_reference_ambiguity,
    )
    write_csv(
        audit_dir / "navaid_duplicate_groups_for_review.csv",
        NAVAID_DUPLICATE_GROUP_REVIEW_COLUMNS,
        navaid_duplicate_groups_for_review,
    )
    write_csv(
        audit_dir / "navaid_ambiguous_references_for_review.csv",
        NAVAID_REFERENCE_AMBIGUITY_COLUMNS,
        navaid_ambiguous_references_for_review,
    )

    report = {
        "airport_rows": len(airports),
        "runway_rows": len(runways),
        "runway_end_rows": len(runway_ends),
        "route_point_rows": len(route_points),
        "airway_rows": len(airways),
        "airway_path_rows": len(airway_paths),
        "airway_occurrence_rows": len(airway_occurrences),
        "procedure_rows": len(procedures),
        "procedure_path_rows": len(procedure_paths),
        "procedure_occurrence_rows": len(procedure_occurrences),
        "route_template_rows": len(route_templates),
        "template_path_rows": len(template_paths),
        "template_token_rows": len(template_tokens),
        "duplicate_key_audit_rows": len(duplicate_rows),
        "unresolved_reference_audit_rows": len(unresolved_rows),
        "rejected_row_audit_rows": len(rejected_rows),
        "sequence_issue_audit_rows": len(sequence_rows),
        "navaid_entity_group_analysis_rows": len(navaid_group_analysis),
        "navaid_entity_group_detail_rows": len(navaid_group_detail),
        "navaid_reference_ambiguity_analysis_rows": len(navaid_reference_ambiguity),
        "navaid_duplicate_groups_for_review_rows": len(navaid_duplicate_groups_for_review),
        "navaid_ambiguous_references_for_review_rows": len(navaid_ambiguous_references_for_review),
        "old_projection_files_generated": 0,
    }
    write_csv(
        audit_dir / "audit_summary.csv",
        AUDIT_SUMMARY_COLUMNS,
        [{"metric": key, "value": value} for key, value in sorted(report.items())],
    )
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="14_May_2026_CSV")
    parser.add_argument("--clean-output", default="data/clean_v1")
    parser.add_argument("--audit-output", default="data/audit_v1")
    args = parser.parse_args()

    report = build_clean_graph_data_v1(
        args.input, args.clean_output, args.audit_output
    )
    for key, value in sorted(report.items()):
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
