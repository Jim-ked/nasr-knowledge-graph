# NASR Knowledge Graph

本项目是“FAA NASR 静态航路语义图 + 路径搜索投影”，不是完整的空管运行知识图谱。

- PreferredRoute、RouteSegment、Airway 和 Procedure 构成可解释、可追溯的航路语义层。
- ROUTE_EDGE 是由已解析 FIX/NAVAID 点链生成的路径搜索投影。
- AIRWAY、DP 和 STAR 当前只建立占位节点，不展开内部点序列。

模型说明见 [docs/data_model.md](docs/data_model.md)。

## 环境配置

```powershell
pip install -r .\requirements.txt
Copy-Item .\.env.example .\.env
```

只需在本地 `.env` 中填写一次真实的 `NEO4J_PASSWORD`。`.env` 不会提交到 Git。

## 第一阶段：生成 clean 数据

```powershell
python .\scripts\build_clean_graph_data.py `
  --input .\14_May_2026_CSV `
  --output .\data\clean
```

清洗同时生成语义层 CSV、搜索投影 CSV 和 `cleaning_report.json`。无法解析的 PFR_SEG 不会被静默丢弃；无对应有效 PreferredRoute 的 segment 不进入语义数据集。

## 第二阶段：导入 Neo4j

```powershell
python .\scripts\import_to_neo4j.py `
  --clean-dir .\data\clean `
  --reset
```

## 第三阶段：验证与审计

```powershell
python .\scripts\validate_neo4j.py

python .\scripts\audit_graph.py `
  --export .\data\audit\graph_audit_report.json
```

审计报告包含节点、关系、孤立节点、机场邻接度、语义航路关联度、航段类型和解析状态等统计。不要使用全图随机绘制判断图谱质量。

## 第四阶段：机场间路径查询

```powershell
python .\scripts\query_route.py `
  --origin ATL `
  --dest LAX `
  --max-depth 40 `
  --limit 3 `
  --neighbor-limit 1000 `
  --max-queue 200000
```

默认查询模式是 Python BFS。Neo4j 每次只提供有向 `ROUTE_EDGE` 邻接边，Python 负责路径去环、深度、结果数量和队列限制。

## 后续范围

后续阶段可继续处理 AWY_BASE、AWY_SEG_ALT、DP/STAR 程序、跑道、空域和频率。天气、NOTAM 与航班动态不属于当前静态 NASR 航路模型。
