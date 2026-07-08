# NASR 静态空中运行路径知识图谱 v1.0

本仓库当前主版本只做一件事：读取 FAA NASR `14_May_2026_CSV/` 原始表，清洗生成静态空中运行路径知识图谱 v1.0 的源事实层 CSV 与审计 CSV。

当前阶段不做 Neo4j 入库，不生成派生搜索边，不做机场间路径搜索投影。

## 当前边界

- 只读取 NASR 静态 CSV 源表。
- 只生成 `data/clean/` 与 `data/audit/`。
- 不生成 `TRAVERSE_TO`。
- 不生成 `USES_POINT`、`USES_AIRWAY`、`USES_PROCEDURE`。
- 不生成旧版路径搜索投影文件。
- 不做实时天气、NOTAM、航班、飞机、机组等外部动态数据。

模型说明见 [docs/data_model.md](docs/data_model.md)。

## 环境

```powershell
python --version
```

清洗脚本只使用 Python 标准库。

## 必需源表

输入目录必须包含以下 NASR 表；缺表会直接终止：

```text
APT_BASE, APT_RWY, APT_RWY_END,
FIX_BASE, NAV_BASE,
AWY_BASE, AWY_SEG_ALT,
DP_BASE, DP_RTE, DP_APT,
STAR_BASE, STAR_RTE, STAR_APT,
PFR_BASE, PFR_SEG,
CDR
```

脚本也会检查核心字段。缺少主键、序列、点名、程序分支等核心字段时会直接报错，不会返回空表继续运行。

## 生成 clean/audit 数据

```powershell
python .\scripts\build_clean_graph_data.py `
  --input .\14_May_2026_CSV `
  --clean-output .\data\clean `
  --audit-output .\data\audit
```

默认输出目录就是：

```text
data/clean/
data/audit/
```

每次运行会先清理目标输出目录中的旧文件，再重新生成本轮结果。

## clean 输出

基础实体：

```text
clean_airports.csv
clean_runways.csv
clean_runway_ends.csv
clean_route_points.csv
```

航路源事实层：

```text
clean_airways.csv
clean_airway_paths.csv
clean_airway_occurrences.csv
rel_airway_has_path.csv
rel_airway_path_has_occurrence.csv
rel_airway_occurrence_resolves_to.csv
rel_next_on_airway.csv
```

程序源事实层：

```text
clean_procedures.csv
clean_procedure_paths.csv
clean_procedure_occurrences.csv
rel_procedure_has_path.csv
rel_procedure_serves_airport.csv
rel_procedure_path_has_occurrence.csv
rel_procedure_occurrence_resolves_to.csv
rel_next_on_procedure.csv
rel_procedure_path_associated_with_runway_end.csv
```

模板源事实层：

```text
clean_route_templates.csv
clean_template_paths.csv
clean_template_tokens.csv
rel_template_origin_ref.csv
rel_template_destination_ref.csv
rel_template_has_path.csv
rel_template_path_has_occurrence.csv
rel_next_template_token.csv
rel_template_token_references.csv
```

机场层补充关系：

```text
rel_airport_has_runway.csv
rel_runway_has_runway_end.csv
```

## audit 输出

```text
audit_duplicate_keys.csv
audit_rejected_rows.csv
audit_sequence_issues.csv
audit_summary.csv
audit_unresolved_references.csv
navaid_entity_group_analysis.csv
navaid_entity_group_detail.csv
navaid_reference_ambiguity_analysis.csv
navaid_duplicate_groups_for_review.csv
navaid_ambiguous_references_for_review.csv
```

Navaid 审计文件只提供机械分析标签与人工审核辅助字段，不输出 `should_merge` / `should_split` 之类的自动建模判断。

## 测试

```powershell
python -m unittest discover -s tests -v
python -m compileall -q scripts tests
```
