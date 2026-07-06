# 数据模型

当前图谱定位为“FAA NASR 静态航路语义图 + 路径搜索投影”，分为两个层次。

## Semantic Graph

- `Airport`：机场。
- `Fix`：航路定位点。
- `Navaid`：导航台。
- `PreferredRoute`：一条 PFR 航路定义，保存航路级属性。
- `RouteSegment`：PFR_SEG 中属于有效语义航路的原始有序段，保存航段级属性。
- `Airway`：PFR_SEG 中 AIRWAY 标识的占位节点，暂不展开内部点序列。
- `Procedure`：PFR_SEG 中 DP 或 STAR 标识的占位节点，暂不展开程序内部点序列。

主要关系：

```text
(Airport)-[:ORIGIN_OF]->(PreferredRoute)
(PreferredRoute)-[:DESTINATION_AIRPORT]->(Airport)
(PreferredRoute)-[:HAS_SEGMENT]->(RouteSegment)
(RouteSegment)-[:NEXT_SEGMENT]->(RouteSegment)
(RouteSegment)-[:REFERENCES]->(Fix|Navaid)
(RouteSegment)-[:USES_AIRWAY]->(Airway)
(RouteSegment)-[:USES_PROCEDURE]->(Procedure)
```

无法展开的 AIRWAY、DP 和 STAR 仍保留占位键，以便追溯原始航段。RADIAL 和 FRD 保留为 RouteSegment，其 `resolvedNodeKey` 暂为空。

## Search Projection

`ROUTE_EDGE` 是由已解析的 FIX/NAVAID 点链派生的有向搜索边，只用于 Python BFS。它不是完整航路语义事实，不替代 PreferredRoute 和 RouteSegment。

双向搜索文件会为缺少反向原始边的关系生成 `synthetic_reverse` 边。边只保存搜索所需属性及 `sourceRouteKeys`，详细航路和航段信息留在语义层。

## 当前边界

当前版本不展开 AWY_BASE、AWY_SEG_ALT、DP/STAR 程序内部结构，也不建模跑道、空域、频率、天气、NOTAM、航班、飞机或机组等动态对象。
