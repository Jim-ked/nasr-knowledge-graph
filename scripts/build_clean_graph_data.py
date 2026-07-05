import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from zipfile import ZipFile


ID_FIELDS = {
    "ARPT_ID",
    "ICAO_ID",
    "SITE_NO",
    "SITE_TYPE_CODE",
    "ORIGIN_ID",
    "DSTN_ID",
    "PFR_TYPE_CODE",
    "ROUTE_NO",
    "SEG_TYPE",
    "SEG_VALUE",
    "FIX_ID",
    "NAV_ID",
    "NAV_TYPE",
    "ICAO_REGION_CODE",
    "STATE_CODE",
    "COUNTRY_CODE",
    "REGION_CODE",
    "ARTCC_ID_HIGH",
    "ARTCC_ID_LOW",
}

AIRPORT_COLUMNS = (
    "nodeKey", "ARPT_ID", "ICAO_ID", "SITE_NO", "SITE_TYPE_CODE",
    "ARPT_NAME", "CITY", "STATE_CODE", "STATE_NAME", "COUNTY_NAME",
    "COUNTRY_CODE", "REGION_CODE", "LAT_DECIMAL", "LONG_DECIMAL", "ELEV",
    "ARPT_STATUS", "FACILITY_USE_CODE", "OWNERSHIP_TYPE_CODE", "FUEL_TYPES",
    "LGT_SKED", "BCN_LGT_SKED", "TWR_TYPE_CODE", "NOTAM_ID", "NOTAM_FLAG",
)

FIX_COLUMNS = (
    "nodeKey", "FIX_ID", "ICAO_REGION_CODE", "STATE_CODE", "COUNTRY_CODE",
    "LAT_DECIMAL", "LONG_DECIMAL", "FIX_USE_CODE", "ARTCC_ID_HIGH",
    "ARTCC_ID_LOW", "COMPULSORY", "CHARTS",
)

NAVAID_COLUMNS = (
    "nodeKey", "NAV_ID", "NAV_TYPE", "NAV_STATUS", "NAME", "CITY",
    "STATE_CODE", "COUNTRY_CODE", "REGION_CODE", "LAT_DECIMAL",
    "LONG_DECIMAL", "FREQ", "OPER_HOURS", "NAS_USE_FLAG", "PUBLIC_USE_FLAG",
)

ROUTE_COLUMNS = (
    "routeKey", "ORIGIN_ID", "DSTN_ID", "PFR_TYPE_CODE", "ROUTE_NO",
    "ALT_DESCRIP", "AIRCRAFT", "HOURS", "ROUTE_DIR_DESCRIP", "DESIGNATOR",
    "ROUTE_STRING",
)

EDGE_COLUMNS = (
    "edgeKey", "fromNodeKey", "toNodeKey", "fromType", "toType",
    "directionType", "sourceRouteCount", "sourceRouteKeys",
)

REJECT_COLUMNS = (
    "routeKey", "ORIGIN_ID", "DSTN_ID", "PFR_TYPE_CODE", "ROUTE_NO",
    "rejectReason",
)


def clean(value):
    value = str(value or "").strip()
    if value.upper() in {"", "NAN", "NONE", "NULL"}:
        return ""
    return value


def clean_id(value):
    return clean(value).upper()


def route_key(row):
    fields = ("ORIGIN_ID", "DSTN_ID", "PFR_TYPE_CODE", "ROUTE_NO")
    return ":".join(clean_id(row.get(field)) for field in fields)


def read_table(input_path, filename):
    input_path = Path(input_path)
    if input_path.suffix.lower() == ".zip":
        with ZipFile(input_path) as archive:
            members = [
                name for name in archive.namelist()
                if Path(name).name.upper() == filename.upper()
            ]
            if not members:
                raise FileNotFoundError(f"{filename} not found in {input_path}")
            with archive.open(members[0]) as raw:
                lines = (line.decode("cp1252") for line in raw)
                return normalize_rows(csv.DictReader(lines))

    with (input_path / filename).open(encoding="cp1252", newline="") as handle:
        return normalize_rows(csv.DictReader(handle))


def normalize_rows(reader):
    rows = []
    for source in reader:
        row = {}
        for field, value in source.items():
            field = clean(field).upper()
            row[field] = clean_id(value) if field in ID_FIELDS else clean(value)
        rows.append(row)
    return rows


def find_input(explicit_input=None):
    if explicit_input:
        return Path(explicit_input)

    candidates = (
        Path("data/raw/14_May_2026_CSV.zip"),
        Path("14_May_2026_CSV.zip"),
        Path("14_May_2026_CSV"),
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("14_May_2026_CSV.zip or folder was not found")


def node_type(node_key):
    return {
        "AIRPORT": "Airport",
        "FIX": "Fix",
        "NAVAID": "Navaid",
    }[node_key.split(":", 1)[0]]


def output_row(row, columns, **extra):
    values = {column: row.get(column, "") for column in columns}
    values.update(extra)
    return values


def write_csv(path, columns, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def build_clean_graph_data(input_path, output_dir):
    input_path = Path(input_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    apt_rows = read_table(input_path, "APT_BASE.csv")
    pfr_rows = read_table(input_path, "PFR_BASE.csv")
    seg_rows = read_table(input_path, "PFR_SEG.csv")
    fix_rows = read_table(input_path, "FIX_BASE.csv")
    nav_rows = read_table(input_path, "NAV_BASE.csv")

    airports = {row["ARPT_ID"]: row for row in apt_rows if row["ARPT_ID"]}
    fixes = {row["FIX_ID"]: row for row in fix_rows if row["FIX_ID"]}
    navaids = {}
    for row in nav_rows:
        key = (row["NAV_ID"], row["NAV_TYPE"])
        if all(key) and key not in navaids:
            navaids[key] = row

    segment_route_keys = {route_key(row) for row in seg_rows}
    valid_before_points = []
    rejected = []

    for row in pfr_rows:
        key = route_key(row)
        reasons = []
        if row["ORIGIN_ID"] not in airports:
            reasons.append("origin_airport_not_found")
        if row["DSTN_ID"] not in airports:
            reasons.append("destination_airport_not_found")
        if key not in segment_route_keys:
            reasons.append("route_segments_not_found")

        if reasons:
            rejected.append(
                output_row(
                    row, REJECT_COLUMNS, routeKey=key,
                    rejectReason="|".join(reasons),
                )
            )
        else:
            valid_before_points.append(row)

    valid_keys = {route_key(row) for row in valid_before_points}
    route_points = defaultdict(list)
    dropped_non_points = 0
    unmatched_fixes = 0
    unmatched_navaids = 0

    for row in seg_rows:
        key = route_key(row)
        if key not in valid_keys:
            continue

        segment_type = row["SEG_TYPE"]
        if segment_type not in {"FIX", "NAVAID"}:
            dropped_non_points += 1
            continue

        if segment_type == "FIX":
            point_id = row["SEG_VALUE"]
            if point_id not in fixes:
                unmatched_fixes += 1
                continue
            point_key = f"FIX:{point_id}"
        else:
            navaid_key = (row["SEG_VALUE"], row["NAV_TYPE"])
            if navaid_key not in navaids:
                unmatched_navaids += 1
                continue
            point_key = f"NAVAID:{navaid_key[0]}:{navaid_key[1]}"

        sequence = float(row["SEGMENT_SEQ"])
        route_points[key].append((sequence, point_key))

    valid_routes = []
    for row in valid_before_points:
        key = route_key(row)
        if route_points[key]:
            valid_routes.append(row)
        else:
            rejected.append(
                output_row(
                    row, REJECT_COLUMNS, routeKey=key,
                    rejectReason="no_fix_or_navaid_after_cleaning",
                )
            )

    airport_ids = {
        row[field]
        for row in valid_routes
        for field in ("ORIGIN_ID", "DSTN_ID")
    }
    fix_ids = set()
    navaid_ids = set()
    edge_sources = defaultdict(set)

    for row in valid_routes:
        key = route_key(row)
        points = [item[1] for item in sorted(route_points[key])]
        for point in points:
            if point.startswith("FIX:"):
                fix_ids.add(point.split(":", 1)[1])
            else:
                _, nav_id, nav_type = point.split(":", 2)
                navaid_ids.add((nav_id, nav_type))

        path = [f"AIRPORT:{row['ORIGIN_ID']}", *points,
                f"AIRPORT:{row['DSTN_ID']}"]
        for start, finish in zip(path, path[1:]):
            if start != finish:
                edge_sources[(start, finish)].add(key)

    original_edges = []
    edge_source_rows = []
    for start, finish in sorted(edge_sources):
        sources = sorted(edge_sources[(start, finish)])
        edge_key = f"{start}->{finish}"
        original_edges.append({
            "edgeKey": edge_key,
            "fromNodeKey": start,
            "toNodeKey": finish,
            "fromType": node_type(start),
            "toType": node_type(finish),
            "directionType": "original",
            "sourceRouteCount": len(sources),
            "sourceRouteKeys": "|".join(sources),
        })
        edge_source_rows.extend(
            {"edgeKey": edge_key, "routeKey": source}
            for source in sources
        )

    bidirectional = list(original_edges)
    original_pairs = set(edge_sources)
    for start, finish in sorted(edge_sources):
        reverse = (finish, start)
        if reverse in original_pairs:
            continue
        sources = sorted(edge_sources[(start, finish)])
        bidirectional.append({
            "edgeKey": f"{finish}->{start}",
            "fromNodeKey": finish,
            "toNodeKey": start,
            "fromType": node_type(finish),
            "toType": node_type(start),
            "directionType": "synthetic_reverse",
            "sourceRouteCount": len(sources),
            "sourceRouteKeys": "|".join(sources),
        })

    airport_output = [
        output_row(
            airports[airport_id], AIRPORT_COLUMNS,
            nodeKey=f"AIRPORT:{airport_id}",
        )
        for airport_id in sorted(airport_ids)
    ]
    fix_output = [
        output_row(fixes[fix_id], FIX_COLUMNS, nodeKey=f"FIX:{fix_id}")
        for fix_id in sorted(fix_ids)
    ]
    navaid_output = [
        output_row(
            navaids[key], NAVAID_COLUMNS,
            nodeKey=f"NAVAID:{key[0]}:{key[1]}",
        )
        for key in sorted(navaid_ids)
    ]
    route_output = [
        output_row(row, ROUTE_COLUMNS, routeKey=route_key(row))
        for row in valid_routes
    ]

    write_csv(output_dir / "clean_airports.csv", AIRPORT_COLUMNS, airport_output)
    write_csv(output_dir / "clean_fixes.csv", FIX_COLUMNS, fix_output)
    write_csv(output_dir / "clean_navaids.csv", NAVAID_COLUMNS, navaid_output)
    write_csv(output_dir / "clean_routes.csv", ROUTE_COLUMNS, route_output)
    write_csv(
        output_dir / "clean_edges_original.csv", EDGE_COLUMNS, original_edges
    )
    write_csv(
        output_dir / "clean_edges_bidirectional.csv",
        EDGE_COLUMNS,
        sorted(bidirectional, key=lambda row: row["edgeKey"]),
    )
    write_csv(
        output_dir / "clean_edge_sources.csv",
        ("edgeKey", "routeKey"),
        edge_source_rows,
    )
    write_csv(output_dir / "rejected_routes.csv", REJECT_COLUMNS, rejected)

    report = {
        "input": str(input_path),
        "apt_base_rows": len(apt_rows),
        "pfr_base_rows": len(pfr_rows),
        "pfr_seg_rows": len(seg_rows),
        "fix_base_rows": len(fix_rows),
        "nav_base_rows": len(nav_rows),
        "valid_routes_before_point_filter": len(valid_before_points),
        "valid_routes_after_point_filter": len(valid_routes),
        "airport_nodes": len(airport_output),
        "fix_nodes": len(fix_output),
        "navaid_nodes": len(navaid_output),
        "route_nodes_total": (
            len(airport_output) + len(fix_output) + len(navaid_output)
        ),
        "original_edges": len(original_edges),
        "bidirectional_edges": len(bidirectional),
        "edge_source_rows": len(edge_source_rows),
        "rejected_routes": len(rejected),
        "dropped_non_point_segments": dropped_non_points,
        "unmatched_fix_points": unmatched_fixes,
        "unmatched_navaid_points": unmatched_navaids,
    }
    with (output_dir / "cleaning_report.json").open(
        "w", encoding="utf-8"
    ) as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input")
    parser.add_argument("--output", default="data/clean")
    args = parser.parse_args()

    report = build_clean_graph_data(find_input(args.input), args.output)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
