# NASR airway source semantics research

Status: evidence capture for review, not a final routing policy.

Scope: FAA NASR AWY source semantics only. This document supports the
`scripts/audit_airway_source_semantics.py` audit outputs and does not define
derived traversal edges.

## Official sources used

The downloaded source list, SHA-256 values, and extracted field evidence are in:

- `data/audit/airway_semantics/official_source_manifest.csv`
- `data/audit/airway_semantics/source_manifest.csv`
- `data/audit/airway_semantics/airway_field_evidence.csv`

Primary references:

- FAA NASR current subscription page, 2026-07-09:
  `https://www.faa.gov/air_traffic/flight_info/aeronav/aero_data/NASR_Subscription/2026-07-09/`
- Legacy TXT to CSV mapping:
  `https://nfdc.faa.gov/webContent/28DaySub/TXT_to_CSV_Mapping.pdf`
- Current AWY CSV package:
  `https://nfdc.faa.gov/webContent/28DaySub/extra/09_Jul_2026_AWY_CSV.zip`
- Current README:
  `https://nfdc.faa.gov/webContent/28DaySub/2026-07-09/README.txt`
- Legacy AWY layout:
  `https://nfdc.faa.gov/webContent/28DaySub/2026-07-09/Layout_Data/awy_rf.txt`
- 2026-09-03 test CSV package:
  `https://nfdc.faa.gov/webContent/28DaySub/Test_Subscriber_Files/NASR_10_1_TEST_CSV.zip`

Important naming note: the mapping PDF discusses legacy `AWY_SEG.csv` and
`AWY_ALT.csv` target names. The current 2026-07-09 AWY CSV ZIP and the
2026-09-03 test CSV ZIP both provide the consolidated file
`AWY_SEG_ALT.csv`.

## Field semantics table

| officialFieldName | currentCleanFieldName | officialDefinition | officialSource | pageOrLocation | allowedValues | graphInterpretation | remainingUncertainty |
|---|---|---|---|---|---|---|---|
| AWY_SEG_ALT row | `clean_airway_occurrences` row plus optional `rel_next_on_airway` to next row | A row is an airway point/segment record ordered by airway id, location, and point sequence. The legacy layout says the airway file consists of individual airway points and the last point is the termination point. | `AWY DATA LAYOUT.pdf`; `awy_rf.txt` | Layout PDF pages 1-2; legacy layout lines 17-22 and 43-45 | One row per `AWY_ID + AWY_LOCATION + POINT_SEQ/FROM_POINT` in the CSV. | Treat the row as a point occurrence. Point-to-next attributes on the same row describe the segment from this point to the next point in sequence. | The final operational traversal policy across gaps is not decided here. |
| POINT_SEQ | `clean_airway_occurrences.pointSeq`; source order for `rel_next_on_airway` | Sequencing number in multiples of ten; points are in order adapted for the airway. | `AWY DATA LAYOUT.pdf`; `TXT_to_CSV_Mapping.pdf` | Layout PDF page 2; mapping PDF pages 16-17 | Numeric sequence, typically multiples of 10. | Sort within `AWY_ID + AWY_LOCATION`; adjacent sorted rows form source adjacency candidates. | Non-numeric values are not expected; the audit sorts them last if encountered for evidence capture. |
| SEG_VALUE | `clean_airway_occurrences.rawFromPoint` via current CSV `FROM_POINT` | Legacy mapping names the point value `SEG_VALUE`; current layout names it `FROM_POINT`, a NAVAID id, fix name, or border crossing. | `TXT_to_CSV_Mapping.pdf`; `AWY DATA LAYOUT.pdf` | Mapping PDF pages 16-17; layout PDF page 2 | NAVAID id, fix name, border crossing generated value. | The node-like source point for an airway occurrence. | Border crossing generated identifiers are source values; no semantic merge is inferred here. |
| NEXT_SEG | `clean_airway_occurrences.rawToPoint`; edge check against next row `rawFromPoint` | Legacy `NEXT_SEG` maps to the current point's following point. Current layout names this `TO_POINT`. | `TXT_to_CSV_Mapping.pdf`; `AWY DATA LAYOUT.pdf` | Mapping PDF page 16; layout PDF page 3 | Empty on terminal or a point value. | Must mechanically match the next sorted row's `FROM_POINT` for non-terminal rows. | The audit does not fuzzy-match similar names. |
| AIRWAY_STRING | `clean_airways.airwayString` / `clean_airway_paths.airwayString` | List of fixes and navaids that make up the airway in order adapted. | `AWY DATA LAYOUT.pdf`; `TXT_to_CSV_Mapping.pdf` | Layout PDF page 2; mapping PDF page 16 | Space-delimited route point tokens in source string. | Audit compares tokens to sorted `FROM_POINT` values for the same airway path. | Formatting differences are reported separately from exact matches; no automatic correction. |
| MAG_COURSE | `rel_next_on_airway.magCourse` | Segment magnetic course. | `AWY DATA LAYOUT.pdf`; `awy_rf.txt` | Layout PDF page 3; legacy layout lines 204-205 | Numeric course or blank. | Attribute on current point-to-next point source segment. | Does not by itself define one-way or two-way traversal policy. |
| OPP_MAG_COURSE | `rel_next_on_airway.oppositeMagCourse` | Segment magnetic course in the opposite direction. | `AWY DATA LAYOUT.pdf`; `awy_rf.txt` | Layout PDF page 3; legacy layout lines 206-207 | Numeric course or blank. | Evidence that source carries opposite-direction attributes for the segment. | Presence of opposite course is evidence, not a final graph edge policy. |
| AWY_SEG_GAP_FLAG | `rel_next_on_airway.gapFlag` | Airway gap flag for discontinued airway; current CSV uses Y/N. | `AWY DATA LAYOUT.pdf`; `TXT_to_CSV_Mapping.pdf`; `awy_rf.txt` | Layout PDF page 4; mapping PDF page 16; legacy layout lines 226-227 | `Y`, `N` in current CSV. | Classify source discontinuity positions; do not decide passability. | Whether a derived traversal layer should cross such rows is deferred. |
| SIGNAL_GAP_FLAG | `rel_next_on_airway.signalGapFlag` | Gap in signal coverage indicator for MEA established with a navigation signal coverage gap; Y/N. | `AWY DATA LAYOUT.pdf`; `awy_rf.txt` | Layout PDF page 4; legacy layout lines 246-250 | `Y`, `N` in current CSV. | Classify signal coverage gaps separately from airway discontinuity. | Signal gap is not automatically a topology break. |
| DOGLEG | `rel_next_on_airway.dogleg` | Turn point not at a navaid; Y/N. Layout note says GPS RNAV routes can mark first, end, and intermediate turn points. | `AWY DATA LAYOUT.pdf`; `awy_rf.txt` | Layout PDF page 4; legacy layout lines 292-294 | `Y`, `N` in current CSV. | Point/turn annotation for audit; not treated as an airway discontinuity. | Operational impact of dogleg is not modeled in this phase. |
| MIN_ENROUTE_ALT | `rel_next_on_airway.minEnrouteAltFt` | Point-to-point minimum enroute altitude. | `AWY DATA LAYOUT.pdf`; `TXT_to_CSV_Mapping.pdf`; `awy_rf.txt` | Layout PDF page 4; mapping PDF page 16; legacy layout lines 211-214 | Numeric feet or blank. | Segment attribute from current point to next point. | Direction-code interpretation remains attribute-level only. |
| MIN_ENROUTE_ALT_OPPOSITE | `rel_next_on_airway.minEnrouteAltOppositeFt` | Point-to-point MEA for the opposite direction. | `AWY DATA LAYOUT.pdf`; `TXT_to_CSV_Mapping.pdf`; `awy_rf.txt` | Layout PDF page 4; mapping PDF page 16; legacy layout lines 215-220 | Numeric feet or blank. | Opposite-direction altitude evidence on the same source segment. | Does not create a derived reverse edge in this phase. |
| MEA_GAP | currently audited from source; not used to create a derived edge | Identifies whether a segment is unusable or has no MEA information. FAA README describes 2026-09 changes using `N` for No MEA, `U` for Unusable, or null. | `AWY DATA LAYOUT.pdf`; `README.txt`; `TXT_to_CSV_Mapping.pdf` | Layout PDF page 5; README coming format changes; mapping PDF page 17 | Current data contains blank, `N`, `U`. | Classify MEA usability separately from airway and signal gaps. | This audit does not decide whether `N` or `U` should block future traversal. |

## Current 14_May_2026 data findings

Generated by:

```powershell
python .\scripts\audit_airway_source_semantics.py `
  --source-dir .\14_May_2026_CSV `
  --clean-dir .\data\clean `
  --output-dir .\data\audit\airway_semantics `
  --future-source-dir <temporary NASR_10_1_TEST_CSV extraction>
```

Key outputs:

- `airway_point_segment_alignment.csv`
- `airway_string_alignment.csv`
- `clean_airway_source_coverage.csv`
- `airway_gap_position_audit.csv`
- `airway_field_value_distribution.csv`
- `nasr_2026_09_schema_change.csv`
- `airway_source_semantics_summary.csv`

Summary:

- Source airway paths: 1,519
- Source point rows: 19,318
- Source expected adjacent rows: 17,799
- Clean airway occurrences: 19,318
- Clean `NEXT_ON_AIRWAY` rows: 17,799
- `NEXT_SEG` / next `POINT_SEQ` mismatches: 0
- Terminal points: 1,519
- Terminal points with non-default segment attributes: 874
- AIRWAY_STRING exact matches: 1,408
- AIRWAY_STRING mismatches: 111
- Source/clean point mismatch paths: 0
- Source/clean edge mismatch paths: 0

Current gap-related counts:

- `AWY_SEG_GAP_FLAG=Y`: 191 rows
- `SIGNAL_GAP_FLAG=Y`: 87 rows
- `MEA_GAP=N`: 218 rows
- `MEA_GAP=U`: 123 rows
- Gap/signal/MEA rows with current clean next edge: 458

Coverage status:

- `exact_point_and_edge_coverage`: 1,277 paths
- `gap_requires_policy`: 242 paths

Direction-code distribution is recorded in
`airway_field_value_distribution.csv`; the values include blank plus compass
codes such as `E BND`, `W BND`, `NE BND`, and related directions.

## Interpretation boundaries

This research phase confirms source structure and current clean coverage. It
does not decide:

- final unidirectional vs bidirectional traversal rules;
- whether to cross `AWY_SEG_GAP_FLAG`, `SIGNAL_GAP_FLAG`, or `MEA_GAP`;
- whether DOGLEG should influence operational routing;
- any derived `TRAVERSE` or `USES` relation.
