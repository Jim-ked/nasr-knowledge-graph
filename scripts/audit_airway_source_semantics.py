import argparse
import csv
import hashlib
import re
from collections import Counter, defaultdict
from pathlib import Path


ALIGNMENT_COLUMNS = (
    "airwayId", "airwayLocation", "pointSeq", "currentSegValue",
    "currentSegType", "nextRowPointSeq", "nextRowSegValue", "nextSegRaw",
    "nextSegMatchesNextRow", "magCourse", "oppMagCourse",
    "magCourseDistance", "gapFlag", "signalGapFlag", "dogleg",
    "isTerminalPoint", "segmentAttributePresent", "sourceRowNumber",
)
STRING_ALIGNMENT_COLUMNS = (
    "airwayId", "airwayLocation", "airwayStringRaw",
    "airwayStringTokens", "orderedSegValues", "tokenCount",
    "pointRowCount", "exactTokenMatch", "normalizedTokenMatch",
    "firstMismatchIndex", "mismatchReason",
)
COVERAGE_COLUMNS = (
    "airwayId", "airwayLocation", "sourcePointRowCount",
    "cleanOccurrenceCount", "sourceExpectedAdjacentEdgeCount",
    "cleanNextEdgeCount", "sourceTerminalPoint", "cleanTerminalPoint",
    "pointCountMatches", "edgeCountMatches", "terminalPointMatches",
    "coverageStatus",
)
GAP_COLUMNS = (
    "airwayId", "airwayLocation", "pointSeq", "currentPoint",
    "nextPoint", "gapFlagActive", "signalGapFlagActive", "meaGapActive",
    "doglegActive", "isTerminalPoint", "hasCurrentCleanNextEdge",
    "gapPositionClass", "sourceRowNumber",
)
FIELD_DISTRIBUTION_COLUMNS = (
    "fieldName", "rawValue", "rowCount", "airwayCount",
    "airwayPathCount", "sampleAirways", "sampleSourceRows",
)
SCHEMA_CHANGE_COLUMNS = (
    "fileName", "changeType", "oldColumn", "newColumn", "oldPosition",
    "newPosition", "impactOnCurrentParser", "recommendedAction",
)
SUMMARY_COLUMNS = ("metric", "value")
SOURCE_MANIFEST_COLUMNS = ("sourceName", "sourcePath", "sha256", "sizeBytes")
FIELD_EVIDENCE_COLUMNS = (
    "officialFieldName", "csvColumn", "officialDefinition",
    "officialSource", "pageOrLocation",
)

SOURCE_REQUIRED = {
    "AWY_BASE": {"AWY_ID", "AWY_LOCATION", "AIRWAY_STRING"},
    "AWY_SEG_ALT": {
        "AWY_ID", "AWY_LOCATION", "POINT_SEQ", "FROM_POINT",
        "FROM_PT_TYPE", "TO_POINT", "MAG_COURSE", "OPP_MAG_COURSE",
        "MAG_COURSE_DIST", "AWY_SEG_GAP_FLAG", "SIGNAL_GAP_FLAG",
        "DOGLEG", "NEXT_MEA_PT", "MIN_ENROUTE_ALT",
        "MIN_ENROUTE_ALT_DIR", "MIN_ENROUTE_ALT_OPPOSITE",
        "MIN_ENROUTE_ALT_OPPOSITE_DIR", "GPS_MIN_ENROUTE_ALT_DIR",
        "GPS_MEA_OPPOSITE_DIR", "MEA_GAP",
    },
}
CLEAN_REQUIRED = {
    "clean_airway_occurrences.csv": {
        "airwayOccurrenceKey", "awyId", "awyLocation", "pointSeq",
        "rawFromPoint",
    },
    "rel_next_on_airway.csv": {"fromKey", "toKey"},
}
FIELD_DISTRIBUTION_FIELDS = (
    "AWY_SEG_GAP_FLAG", "SIGNAL_GAP_FLAG", "DOGLEG", "MEA_GAP",
    "MIN_ENROUTE_ALT_DIR", "MIN_ENROUTE_ALT_OPPOSITE_DIR",
    "GPS_MIN_ENROUTE_ALT_DIR", "GPS_MEA_OPPOSITE_DIR",
)
SEGMENT_ATTRIBUTE_FIELDS = (
    "TO_POINT", "MAG_COURSE", "OPP_MAG_COURSE", "MAG_COURSE_DIST",
    "NEXT_MEA_PT", "MIN_ENROUTE_ALT", "MIN_ENROUTE_ALT_OPPOSITE",
    "MEA_GAP",
)
CURRENT_PARSER_COLUMNS = {
    "AWY_BASE": {"AWY_ID", "AWY_LOCATION", "AIRWAY_STRING"},
    "AWY_SEG_ALT": SOURCE_REQUIRED["AWY_SEG_ALT"],
}
OFFICIAL_FIELD_EVIDENCE = (
    ("POINT_SEQ", "POINT_SEQ", "Sequencing number in multiples of ten. Points are in order adapted for given Airway.", "AWY DATA LAYOUT.pdf", "page 2"),
    ("SEG_VALUE", "FROM_POINT", "NAVAID Facility Identifier, FIX Name or Border crossing.", "AWY DATA LAYOUT.pdf", "page 2; TXT_to_CSV_Mapping.pdf pages 16-17 maps AWY2 point value to SEG_VALUE"),
    ("NEXT_SEG", "TO_POINT", "The To Point that directly follows the current From Point on an individual segment.", "AWY DATA LAYOUT.pdf", "page 3; TXT_to_CSV_Mapping.pdf page 16 maps legacy NEXT_SEG"),
    ("AIRWAY_STRING", "AIRWAY_STRING", "List of FIX and NAVAID that make up the AIRWAY in order adapted.", "AWY DATA LAYOUT.pdf", "page 2"),
    ("MAG_COURSE", "MAG_COURSE", "Segment Magnetic Course.", "AWY DATA LAYOUT.pdf", "page 3"),
    ("OPP_MAG_COURSE", "OPP_MAG_COURSE", "Segment Magnetic Course - Opposite Direction.", "AWY DATA LAYOUT.pdf", "page 3"),
    ("AWY_SEG_GAP_FLAG", "AWY_SEG_GAP_FLAG", "Airway Gap Flag Indicator for when Airway Discontinued - Y/N.", "AWY DATA LAYOUT.pdf", "page 4"),
    ("SIGNAL_GAP_FLAG", "SIGNAL_GAP_FLAG", "Gap in Signal Coverage Indicator for when MEA established with a gap in navigation signal coverage - Y/N.", "AWY DATA LAYOUT.pdf", "page 4"),
    ("DOGLEG", "DOGLEG", "A Turn Point Not At A NAVAID - Y/N.", "AWY DATA LAYOUT.pdf", "page 4"),
    ("MIN_ENROUTE_ALT", "MIN_ENROUTE_ALT", "Point To Point Minimum Enroute Altitude (MEA).", "AWY DATA LAYOUT.pdf", "page 4"),
    ("MIN_ENROUTE_ALT_OPPOSITE", "MIN_ENROUTE_ALT_OPPOSITE", "Point To Point Minimum Enroute Altitude (MEA-Opposite Direction).", "AWY DATA LAYOUT.pdf", "page 4"),
    ("MEA_GAP", "MEA_GAP", "Identifies whether a given Airway Segment is Unusable or contains No MEA information.", "AWY DATA LAYOUT.pdf", "page 5; README.txt 2026-09 format change note"),
)


def normalize(value):
    text = str(value or "").strip().upper()
    text = re.sub(r"[\s\-_]+", "", text)
    return text


def bool_text(value):
    return "true" if value else "false"


def flag_active(value):
    return normalize(value) not in {"", "N", "NO", "0", "FALSE"}


def numeric_point_seq(value):
    text = str(value or "").strip()
    if not text:
        return 10**9
    try:
        return int(float(text))
    except ValueError:
        return 10**9


def read_csv(path, required_columns=None):
    if not path.exists():
        raise ValueError(f"Missing required CSV: {path}")
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if required_columns:
        missing = sorted(required_columns - set(rows[0].keys() if rows else []))
        if missing:
            raise ValueError(f"Missing required columns in {path.name}: {', '.join(missing)}")
    return rows


def write_csv(path, columns, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def find_case_insensitive(directory, names):
    if not Path(directory).exists():
        raise ValueError(f"Missing directory: {directory}")
    index = {item.name.upper(): item for item in Path(directory).iterdir() if item.is_file()}
    for name in names:
        found = index.get(name.upper())
        if found:
            return found
    raise ValueError(f"Missing required source file, expected one of: {', '.join(names)}")


def load_source_tables(source_dir):
    base_path = find_case_insensitive(source_dir, ["AWY_BASE.csv"])
    seg_path = find_case_insensitive(source_dir, ["AWY_SEG_ALT.csv", "AWY_SEG.csv"])
    tables = {
        "AWY_BASE": read_csv(base_path, SOURCE_REQUIRED["AWY_BASE"]),
        "AWY_SEG_ALT": read_csv(seg_path, SOURCE_REQUIRED["AWY_SEG_ALT"]),
    }
    add_source_row_numbers(tables["AWY_BASE"])
    add_source_row_numbers(tables["AWY_SEG_ALT"])
    return tables, {"AWY_BASE": base_path, "AWY_SEG_ALT": seg_path}


def add_source_row_numbers(rows):
    for index, row in enumerate(rows, start=2):
        row["_sourceRowNumber"] = str(index)


def load_clean_tables(clean_dir):
    return {
        name: read_csv(Path(clean_dir) / name, required)
        for name, required in CLEAN_REQUIRED.items()
    }


def group_airway_points(seg_rows):
    groups = defaultdict(list)
    for row in seg_rows:
        item = dict(row)
        groups[(row["AWY_ID"], row["AWY_LOCATION"])].append(item)
    for key in groups:
        groups[key].sort(key=lambda row: (numeric_point_seq(row["POINT_SEQ"]), row["POINT_SEQ"], row["_sourceRowNumber"]))
    return groups


def airway_point_segment_alignment(seg_rows):
    output = []
    for (awy_id, location), rows in sorted(group_airway_points(seg_rows).items()):
        for index, row in enumerate(rows):
            next_row = rows[index + 1] if index + 1 < len(rows) else None
            terminal = next_row is None
            next_value = next_row["FROM_POINT"] if next_row else ""
            output.append({
                "airwayId": awy_id,
                "airwayLocation": location,
                "pointSeq": row["POINT_SEQ"],
                "currentSegValue": row["FROM_POINT"],
                "currentSegType": row.get("FROM_PT_TYPE", ""),
                "nextRowPointSeq": next_row["POINT_SEQ"] if next_row else "",
                "nextRowSegValue": next_value,
                "nextSegRaw": row.get("TO_POINT", ""),
                "nextSegMatchesNextRow": "" if terminal else bool_text(normalize(row.get("TO_POINT")) == normalize(next_value)),
                "magCourse": row.get("MAG_COURSE", ""),
                "oppMagCourse": row.get("OPP_MAG_COURSE", ""),
                "magCourseDistance": row.get("MAG_COURSE_DIST", ""),
                "gapFlag": row.get("AWY_SEG_GAP_FLAG", ""),
                "signalGapFlag": row.get("SIGNAL_GAP_FLAG", ""),
                "dogleg": row.get("DOGLEG", ""),
                "isTerminalPoint": bool_text(terminal),
                "segmentAttributePresent": bool_text(segment_attribute_present(row)),
                "sourceRowNumber": row["_sourceRowNumber"],
            })
    return output


def airway_string_alignment(base_rows, seg_rows):
    point_groups = group_airway_points(seg_rows)
    output = []
    for row in sorted(base_rows, key=lambda item: (item["AWY_ID"], item["AWY_LOCATION"])):
        key = (row["AWY_ID"], row["AWY_LOCATION"])
        tokens = [token for token in row.get("AIRWAY_STRING", "").split() if token]
        ordered = [item["FROM_POINT"] for item in point_groups.get(key, [])]
        exact = tokens == ordered
        normalized_tokens = [normalize(token) for token in tokens]
        normalized_ordered = [normalize(token) for token in ordered]
        normalized_match = normalized_tokens == normalized_ordered
        mismatch_index, reason = first_mismatch(tokens, ordered, exact, normalized_match)
        output.append({
            "airwayId": row["AWY_ID"],
            "airwayLocation": row["AWY_LOCATION"],
            "airwayStringRaw": row.get("AIRWAY_STRING", ""),
            "airwayStringTokens": "|".join(tokens),
            "orderedSegValues": "|".join(ordered),
            "tokenCount": len(tokens),
            "pointRowCount": len(ordered),
            "exactTokenMatch": bool_text(exact),
            "normalizedTokenMatch": bool_text(normalized_match),
            "firstMismatchIndex": mismatch_index,
            "mismatchReason": reason,
        })
    return output


def first_mismatch(tokens, ordered, exact, normalized_match):
    if exact:
        return "", "exact_match"
    if normalized_match:
        return "", "normalized_match"
    limit = min(len(tokens), len(ordered))
    for index in range(limit):
        if normalize(tokens[index]) != normalize(ordered[index]):
            return str(index), "token_value_mismatch"
    if len(tokens) != len(ordered):
        return str(limit), "token_count_mismatch"
    return "", "unknown_mismatch"


def clean_coverage(seg_rows, clean_tables):
    source_groups = group_airway_points(seg_rows)
    occ_rows = clean_tables["clean_airway_occurrences.csv"]
    rel_rows = clean_tables["rel_next_on_airway.csv"]
    occ_by_key = {row["airwayOccurrenceKey"]: row for row in occ_rows}
    occ_by_path = defaultdict(list)
    for row in occ_rows:
        occ_by_path[(row["awyId"], row["awyLocation"])].append(row)
    next_by_path = Counter()
    outgoing = defaultdict(set)
    for rel in rel_rows:
        from_occ = occ_by_key.get(rel["fromKey"])
        if from_occ:
            key = (from_occ["awyId"], from_occ["awyLocation"])
            next_by_path[key] += 1
            outgoing[key].add(rel["fromKey"])
    output = []
    for key in sorted(set(source_groups) | set(occ_by_path)):
        source = source_groups.get(key, [])
        clean = sorted(occ_by_path.get(key, []), key=lambda row: (numeric_point_seq(row["pointSeq"]), row["pointSeq"]))
        expected_edges = max(len(source) - 1, 0)
        source_terminal = source[-1]["FROM_POINT"] if source else ""
        clean_terminal = clean_terminal_point(clean, outgoing.get(key, set()))
        point_match = len(source) == len(clean)
        edge_match = expected_edges == next_by_path.get(key, 0)
        terminal_match = normalize(source_terminal) == normalize(clean_terminal)
        has_gap = any(row_has_gap(row) for row in source)
        source_consistent = all(
            normalize(source[i].get("TO_POINT")) == normalize(source[i + 1].get("FROM_POINT"))
            for i in range(max(len(source) - 1, 0))
        )
        if not source_consistent:
            status = "source_data_inconsistent"
        elif not point_match:
            status = "point_count_mismatch"
        elif not edge_match:
            status = "edge_count_mismatch"
        elif not terminal_match:
            status = "terminal_point_mismatch"
        elif has_gap:
            status = "gap_requires_policy"
        else:
            status = "exact_point_and_edge_coverage"
        output.append({
            "airwayId": key[0],
            "airwayLocation": key[1],
            "sourcePointRowCount": len(source),
            "cleanOccurrenceCount": len(clean),
            "sourceExpectedAdjacentEdgeCount": expected_edges,
            "cleanNextEdgeCount": next_by_path.get(key, 0),
            "sourceTerminalPoint": source_terminal,
            "cleanTerminalPoint": clean_terminal,
            "pointCountMatches": bool_text(point_match),
            "edgeCountMatches": bool_text(edge_match),
            "terminalPointMatches": bool_text(terminal_match),
            "coverageStatus": status,
        })
    return output


def clean_terminal_point(clean_rows, outgoing_keys):
    for row in clean_rows:
        if row["airwayOccurrenceKey"] not in outgoing_keys:
            return row["rawFromPoint"]
    return clean_rows[-1]["rawFromPoint"] if clean_rows else ""


def row_has_gap(row):
    return (
        flag_active(row.get("AWY_SEG_GAP_FLAG"))
        or flag_active(row.get("SIGNAL_GAP_FLAG"))
        or normalize(row.get("MEA_GAP")) in {"U", "N"}
    )


def segment_attribute_present(row):
    if any(str(row.get(field, "")).strip() for field in SEGMENT_ATTRIBUTE_FIELDS):
        return True
    return flag_active(row.get("AWY_SEG_GAP_FLAG")) or flag_active(row.get("SIGNAL_GAP_FLAG"))


def gap_position_audit(seg_rows, clean_tables):
    source_groups = group_airway_points(seg_rows)
    edge_from_keys = {row["fromKey"] for row in clean_tables["rel_next_on_airway.csv"]}
    output = []
    for (awy_id, location), rows in sorted(source_groups.items()):
        for index, row in enumerate(rows):
            gap = flag_active(row.get("AWY_SEG_GAP_FLAG"))
            signal = flag_active(row.get("SIGNAL_GAP_FLAG"))
            mea = normalize(row.get("MEA_GAP")) in {"U", "N"}
            dogleg = flag_active(row.get("DOGLEG"))
            if not (gap or signal or mea or dogleg):
                continue
            terminal = index + 1 == len(rows)
            occ_key = f"AWY_OCC:{awy_id}:{location}:{row['POINT_SEQ']}"
            output.append({
                "airwayId": awy_id,
                "airwayLocation": location,
                "pointSeq": row["POINT_SEQ"],
                "currentPoint": row["FROM_POINT"],
                "nextPoint": row.get("TO_POINT", ""),
                "gapFlagActive": bool_text(gap),
                "signalGapFlagActive": bool_text(signal),
                "meaGapActive": bool_text(mea),
                "doglegActive": bool_text(dogleg),
                "isTerminalPoint": bool_text(terminal),
                "hasCurrentCleanNextEdge": bool_text(occ_key in edge_from_keys),
                "gapPositionClass": gap_position_class(gap, signal, mea, dogleg, terminal),
                "sourceRowNumber": row["_sourceRowNumber"],
            })
    return output


def gap_position_class(gap, signal, mea, dogleg, terminal):
    active_count = sum(1 for value in (gap, signal, mea) if value)
    if active_count > 1:
        return "multiple_flags" if not (gap and signal and not mea) else "airway_and_signal_gap"
    if gap:
        return "airway_discontinuity"
    if signal:
        return "signal_coverage_gap"
    if mea:
        return "mea_unusable"
    if terminal:
        return "terminal_flag"
    if dogleg:
        return "dogleg_turn_point"
    return "unknown"


def field_value_distribution(seg_rows):
    output = []
    for field in FIELD_DISTRIBUTION_FIELDS:
        groups = defaultdict(list)
        for row in seg_rows:
            groups[row.get(field, "")].append(row)
        for raw, rows in sorted(groups.items(), key=lambda item: (item[0] != "", item[0])):
            output.append({
                "fieldName": field,
                "rawValue": raw,
                "rowCount": len(rows),
                "airwayCount": len({row["AWY_ID"] for row in rows}),
                "airwayPathCount": len({(row["AWY_ID"], row["AWY_LOCATION"]) for row in rows}),
                "sampleAirways": "|".join(sorted({row["AWY_ID"] for row in rows})[:10]),
                "sampleSourceRows": "|".join(row["_sourceRowNumber"] for row in rows[:10]),
            })
    return output


def schema_change_rows(source_dir, future_source_dir):
    if not future_source_dir:
        return []
    current = schema_headers(source_dir)
    future = schema_headers(future_source_dir)
    rows = []
    for file_name in sorted(set(current) | set(future)):
        old_cols = current.get(file_name, [])
        new_cols = future.get(file_name, [])
        old_pos = {col: i + 1 for i, col in enumerate(old_cols)}
        new_pos = {col: i + 1 for i, col in enumerate(new_cols)}
        for col in old_cols:
            if col not in new_pos:
                rows.append(schema_row(file_name, "removed", col, "", old_pos[col], "", col))
            elif old_pos[col] != new_pos[col]:
                rows.append(schema_row(file_name, "reordered", col, col, old_pos[col], new_pos[col], col))
            else:
                rows.append(schema_row(file_name, "unchanged", col, col, old_pos[col], new_pos[col], col))
        for col in new_cols:
            if col not in old_pos:
                rows.append(schema_row(file_name, "added", "", col, "", new_pos[col], col))
    return rows


def schema_headers(directory):
    headers = {}
    for logical, names in {
        "AWY_BASE": ["AWY_BASE.csv"],
        "AWY_SEG_ALT": ["AWY_SEG_ALT.csv", "AWY_SEG.csv"],
    }.items():
        try:
            path = find_case_insensitive(directory, names)
        except ValueError:
            continue
        with path.open(encoding="utf-8-sig", newline="") as handle:
            headers[logical] = next(csv.reader(handle))
    return headers


def schema_row(file_name, change_type, old_col, new_col, old_pos, new_pos, parser_col):
    used = parser_col in CURRENT_PARSER_COLUMNS.get(file_name, set())
    return {
        "fileName": file_name,
        "changeType": change_type,
        "oldColumn": old_col,
        "newColumn": new_col,
        "oldPosition": old_pos,
        "newPosition": new_pos,
        "impactOnCurrentParser": "current_parser_uses_column" if used else "not_used_by_current_audit",
        "recommendedAction": "review_before_parser_change" if used and change_type != "unchanged" else "no_parser_change_now",
    }


def source_manifest(paths):
    rows = []
    for name, path in paths.items():
        rows.append({
            "sourceName": name,
            "sourcePath": str(path),
            "sha256": sha256(path),
            "sizeBytes": path.stat().st_size,
        })
    return rows


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def field_evidence_rows():
    return [
        {
            "officialFieldName": item[0],
            "csvColumn": item[1],
            "officialDefinition": item[2],
            "officialSource": item[3],
            "pageOrLocation": item[4],
        }
        for item in OFFICIAL_FIELD_EVIDENCE
    ]


def summary_rows(alignment, string_alignment, coverage, gaps):
    return [
        ("sourceAirwayPathCount", len({(row["airwayId"], row["airwayLocation"]) for row in alignment})),
        ("sourcePointRowCount", len(alignment)),
        ("sourceExpectedAdjacentEdgeCount", sum(1 for row in alignment if row["isTerminalPoint"] == "false")),
        ("cleanOccurrenceCount", sum(int(row["cleanOccurrenceCount"]) for row in coverage)),
        ("cleanNextEdgeCount", sum(int(row["cleanNextEdgeCount"]) for row in coverage)),
        ("airwayStringExactMatchCount", sum(1 for row in string_alignment if row["exactTokenMatch"] == "true")),
        ("airwayStringMismatchCount", sum(1 for row in string_alignment if row["exactTokenMatch"] != "true")),
        ("nextSegMatchCount", sum(1 for row in alignment if row["nextSegMatchesNextRow"] == "true")),
        ("nextSegMismatchCount", sum(1 for row in alignment if row["nextSegMatchesNextRow"] == "false")),
        ("terminalPointCount", sum(1 for row in alignment if row["isTerminalPoint"] == "true")),
        ("terminalWithSegmentAttributesCount", sum(1 for row in alignment if row["isTerminalPoint"] == "true" and row["segmentAttributePresent"] == "true")),
        ("airwayGapCount", sum(1 for row in gaps if row["gapFlagActive"] == "true")),
        ("signalGapCount", sum(1 for row in gaps if row["signalGapFlagActive"] == "true")),
        ("meaGapCount", sum(1 for row in gaps if row["meaGapActive"] == "true")),
        ("gapWithCleanNextEdgeCount", sum(
            1 for row in gaps
            if row["hasCurrentCleanNextEdge"] == "true"
            and (
                row["gapFlagActive"] == "true"
                or row["signalGapFlagActive"] == "true"
                or row["meaGapActive"] == "true"
            )
        )),
        ("sourceCleanPointMismatchPathCount", sum(1 for row in coverage if row["pointCountMatches"] != "true")),
        ("sourceCleanEdgeMismatchPathCount", sum(1 for row in coverage if row["edgeCountMatches"] != "true")),
    ]


def audit_airway_source_semantics(source_dir, clean_dir, output_dir, future_source_dir=None):
    tables, paths = load_source_tables(source_dir)
    clean = load_clean_tables(clean_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    alignment = airway_point_segment_alignment(tables["AWY_SEG_ALT"])
    string_alignment = airway_string_alignment(tables["AWY_BASE"], tables["AWY_SEG_ALT"])
    coverage = clean_coverage(tables["AWY_SEG_ALT"], clean)
    gaps = gap_position_audit(tables["AWY_SEG_ALT"], clean)
    distribution = field_value_distribution(tables["AWY_SEG_ALT"])
    schema_changes = schema_change_rows(source_dir, future_source_dir)
    summary = [{"metric": metric, "value": value} for metric, value in summary_rows(alignment, string_alignment, coverage, gaps)]

    write_csv(output_dir / "airway_point_segment_alignment.csv", ALIGNMENT_COLUMNS, alignment)
    write_csv(output_dir / "airway_string_alignment.csv", STRING_ALIGNMENT_COLUMNS, string_alignment)
    write_csv(output_dir / "clean_airway_source_coverage.csv", COVERAGE_COLUMNS, coverage)
    write_csv(output_dir / "airway_gap_position_audit.csv", GAP_COLUMNS, gaps)
    write_csv(output_dir / "airway_field_value_distribution.csv", FIELD_DISTRIBUTION_COLUMNS, distribution)
    write_csv(output_dir / "nasr_2026_09_schema_change.csv", SCHEMA_CHANGE_COLUMNS, schema_changes)
    write_csv(output_dir / "airway_source_semantics_summary.csv", SUMMARY_COLUMNS, summary)
    write_csv(output_dir / "source_manifest.csv", SOURCE_MANIFEST_COLUMNS, source_manifest(paths))
    write_csv(output_dir / "airway_field_evidence.csv", FIELD_EVIDENCE_COLUMNS, field_evidence_rows())
    return {row["metric"]: row["value"] for row in summary}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", required=True)
    parser.add_argument("--clean-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--future-source-dir")
    args = parser.parse_args()
    counts = audit_airway_source_semantics(
        args.source_dir, args.clean_dir, args.output_dir, args.future_source_dir
    )
    for key in sorted(counts):
        print(f"{key}: {counts[key]}")


if __name__ == "__main__":
    main()
