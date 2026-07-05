# NASR Knowledge Graph Research

本仓库当前仅保存 `14_May_2026_CSV` 原始数据。

知识图谱结构尚未确定。下一步先检查数据表、字段、主键、外键和业务语义，
形成经过审查的数据模型后，再开始编写导入代码。

## 第一阶段：生成清洗数据

```powershell
python .\scripts\build_clean_graph_data.py `
  --input .\14_May_2026_CSV `
  --output .\data\clean
```

脚本只读取：

- `APT_BASE.csv`
- `PFR_BASE.csv`
- `PFR_SEG.csv`
- `FIX_BASE.csv`
- `NAV_BASE.csv`

当前阶段不连接 Neo4j。清洗统计见
[`data/clean/cleaning_report.json`](data/clean/cleaning_report.json)。

## 第二阶段：导入与查询

```powershell
pip install -r .\requirements.txt

$env:NEO4J_URI = 'bolt://localhost:7687'
$env:NEO4J_USER = 'neo4j'
$env:NEO4J_PASSWORD = '真实密码'

python .\scripts\import_to_neo4j.py --clean-dir .\data\clean --reset
python .\scripts\validate_neo4j.py
python .\scripts\query_route.py --origin ATL --dest LAX --max-depth 40 --limit 10
```

数据库只创建 `Airport`、`Fix`、`Navaid` 三类节点标签以及
`ROUTE_EDGE` 关系，不创建公共 `RouteNode` 标签。节点的 `displayName`
用于 Browser 标题；可通过 `:style` 导入
[`browser_style.grass`](browser_style.grass)。

查询只沿 `ROUTE_EDGE ->` 前进，因为
`clean_edges_bidirectional.csv` 已经显式包含反向边。路径查询同时限制最大深度、
禁止节点重复、禁止中间机场，并通过 `SHORTEST k` 限制返回数量。
