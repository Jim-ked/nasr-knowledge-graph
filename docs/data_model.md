# NASR 静态空中运行路径知识图谱 v1.0 数据模型

v1.0 的目标是建立可审计、可追溯的 NASR 静态空中运行路径源事实层。当前版本先把源表事实清洗成节点表、关系表和审计表，暂不生成路径搜索派生层。

## 统一约定

所有节点和关键关系都保留：

```text
sourceCycle = 2026-05-14
sourceTable = 原始 NASR CSV 表名
sourceRowId = 原始 CSV 行号
```

解析类关系还保留：

```text
rawValue
normalizedValue
resolveMethod
resolveStatus
confidence
```

## 基础实体

```text
Airport
Runway
RunwayEnd
RoutePoint
```

`RoutePoint` 用 `pointType` 区分：

```text
FIX
NAVAID
BOUNDARY
```

Navaid 当前不自动合并同 `NAV_ID + NAV_TYPE` 的记录。主键使用包含位置上下文的 `currentPointKey`，重复组只进入 audit 文件供人工判断。

## 航路源事实层

```text
Airway
AirwayPath
AirwayPointOccurrence
```

主要关系：

```text
(Airway)-[:HAS_PATH]->(AirwayPath)
(AirwayPath)-[:HAS_OCCURRENCE]->(AirwayPointOccurrence)
(AirwayPointOccurrence)-[:RESOLVES_TO]->(RoutePoint)
(AirwayPointOccurrence)-[:NEXT_ON_AIRWAY]->(AirwayPointOccurrence)
```

`NEXT_ON_AIRWAY` 只表示 `AWY_SEG_ALT` 中同一 `airwayPathKey` 内按 `POINT_SEQ` 的源表顺序。

## 程序源事实层

```text
Procedure
ProcedurePath
ProcedurePointOccurrence
```

主要关系：

```text
(Procedure)-[:HAS_PATH]->(ProcedurePath)
(Procedure)-[:SERVES_AIRPORT]->(Airport)
(ProcedurePath)-[:HAS_OCCURRENCE]->(ProcedurePointOccurrence)
(ProcedurePointOccurrence)-[:RESOLVES_TO]->(RoutePoint)
(ProcedurePointOccurrence)-[:NEXT_ON_PROCEDURE]->(ProcedurePointOccurrence)
(ProcedurePath)-[:ASSOCIATED_WITH_RUNWAY_END]->(RunwayEnd)
```

`ProcedurePath` 是多行 `DP_RTE` / `STAR_RTE` 聚合出的分支，因此包含：

```text
sourceAggregation
sourceRowIds
sourceRowCount
```

程序方向只按源表序列保留，不在 v1.0 中进入路径搜索层。

## 模板源事实层

```text
RouteTemplate
TemplatePath
TemplateTokenOccurrence
```

`PFR_BASE/PFR_SEG` 生成结构化模板；`CDR` 第一版只作为 `raw_only` 模板保留。

主要关系：

```text
(RouteTemplate)-[:ORIGIN_REF]->(Airport | RoutePoint)
(RouteTemplate)-[:DESTINATION_REF]->(Airport | RoutePoint)
(RouteTemplate)-[:HAS_PATH]->(TemplatePath)
(TemplatePath)-[:HAS_OCCURRENCE]->(TemplateTokenOccurrence)
(TemplateTokenOccurrence)-[:NEXT_TEMPLATE_TOKEN]->(TemplateTokenOccurrence)
(TemplateTokenOccurrence)-[:REFERENCES]->(RoutePoint | Airway | Procedure)
```

`RADIAL` / `FRD` token 当前保留为 unsupported，不强行解析。

## 审计层

审计输出用于人工检查建模规则，包括：

```text
重复 key
异常或被拒绝的源行
未解析引用
序列一致性问题
Navaid 重复组分析
Navaid 引用歧义分析
```

Navaid 审计只输出机械标签，例如：

```text
single_record
same_name_same_city_same_coord
same_id_type_different_state
same_id_type_different_city
same_id_type_different_freq
same_id_type_missing_location
insufficient_fields
```

不输出自动合并/拆分判断。

## 当前不做

v1.0 暂不生成：

```text
TRAVERSE_TO
USES_POINT
USES_AIRWAY
USES_PROCEDURE
```

也暂不提供 Neo4j 入库脚本和机场间路径搜索主流程。后续若要做路径搜索，应在本源事实层通过审核后，再单独设计派生层。
