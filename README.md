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
