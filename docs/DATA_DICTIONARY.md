# PortPulse 数据字典 v1

> 本文定义 PortPulse 对外 API 的字段、取值范围与时间/单位约定。  
> 稳定锚点（例如 `#dict-ports-snapshot`）可供 OpenAPI/README/工单链接。

---

## 1. meta

<a id="dict-meta-sources"></a>
### 1.1 `/v1/sources`（数据来源列表）
| 字段 | 类型 | 说明 |
|---|---|---|
| id | integer | 自增 ID |
| name | string | 数据源名称 |
| url | string | 官网或来源链接 |
| last_updated | timestamptz | 数据源更新时间（UTC ISO8601） |

---

## 2. ports（港口）

统一约定：
- `unlocode`: 港口 UN/LOCODE，示例：`USLAX`（洛杉矶）。
- 时间：除特别说明外，均为 **UTC**。
- 小数：`avg_wait_hours`、`dwell_hours` 等为小时数（可含小数）。

<a id="dict-ports-snapshot"></a>
### 2.1 `/v1/ports/{unlocode}/snapshot`
返回最近一条快照。**顶层永不返回 null**；无数据时 `snapshot` 为 `null`。
| 字段 | 类型 | 说明 |
|---|---|---|
| unlocode | string | 港口代码 |
| snapshot | object \| null | 见下表；无数据时为 null |
| ├─ snapshot_ts | timestamptz | 快照时间（UTC） |
| ├─ vessels | integer | 在港/周边船舶数 |
| ├─ avg_wait_hours | number | 平均等泊小时 |
| ├─ congestion_score | number | 拥堵评分（0–100） |
| ├─ src | string | 数据来源标识（如 `prod`） |
| └─ src_loaded_at | timestamptz | 数据装载时间（UTC） |

<a id="dict-ports-dwell"></a>
### 2.2 `/v1/ports/{unlocode}/dwell?days=N`
返回近 N 天的每日停时序列。
| 字段 | 类型 | 说明 |
|---|---|---|
| unlocode | string | 港口代码 |
| points | array | 序列（可能为空数组） |
| 每个 point: |  |  |
| ├─ date | date(YYYY-MM-DD) | 自然日（UTC） |
| ├─ dwell_hours | number | 当日平均停时（小时） |
| └─ src | string | 数据来源标识 |

<a id="dict-ports-overview"></a>
### 2.3 `/v1/ports/{unlocode}/overview?format=json|csv`
聚合视图（便于看板/报表）。
| 字段 | 类型 | 说明 |
|---|---|---|
| unlocode | string | 港口代码 |
| as_of | timestamptz | 数据时点（UTC） |
| metrics | object | 指标包 |
| ├─ vessels | integer | 船舶数 |
| ├─ avg_wait_hours | number | 等泊小时 |
| └─ congestion_score | number | 拥堵评分 |
| source | object | 来源信息 |
| ├─ src | string | 数据来源标识 |
| └─ src_loaded_at | timestamptz | 装载时间（UTC） |

<a id="dict-ports-alerts"></a>
### 2.4 `/v1/ports/{unlocode}/alerts?window=14d`
窗口期内的告警（示例：停时显著变化）。
| 字段 | 类型 | 说明 |
|---|---|---|
| unlocode | string | 港口代码 |
| window_days | integer | 窗口大小（天） |
| alerts | array | 告警列表 |
| 每个 alert: |  |  |
| ├─ type | string | 告警类型（如 `dwell_change`） |
| ├─ latest | number | 窗口后半段均值/最新值 |
| ├─ baseline | number | 窗口前半段均值 |
| ├─ change | number | `latest - baseline` |
| └─ note | string | 备注说明（可能含 Unicode 符号） |

<a id="dict-ports-trend"></a>
### 2.5 `/v1/ports/{unlocode}/trend?days=...&fields=...`
返回多指标逐日趋势。空指标以 `null` 占位，**永不抛 500**。
| 字段 | 类型 | 说明 |
|---|---|---|
| unlocode | string | 港口代码 |
| days | integer | 回溯天数 |
| points | array | 序列（可能为空） |
| 每个 point: |  |  |
| ├─ date | date | 日期 |
| ├─ src | string | 数据来源标识 |
| ├─ vessels | integer \| null | 船舶数 |
| ├─ avg_wait_hours | number \| null | 等泊小时 |
| └─ congestion_score | number \| null | 拥堵评分 |

---

## 3. trade（贸易）

<a id="dict-trade-hs-imports"></a>
### 3.1 `/v1/hs/{code}/imports?frm=YYYY-MM&to=YYYY-MM`
| 字段 | 类型 | 说明 |
|---|---|---|
| code | string | HS 编码（2/4/6/8 位） |
| frm/to | string | 月度区间（闭区间） |
| 返回 | array | 按 period 升序 |
| 每项： |  |  |
| ├─ code | string | HS 编码 |
| ├─ country | string | 国家/地区 |
| ├─ period | string | 形如 `2025-08` |
| ├─ value_usd | number | 金额（美元） |
| └─ qty / unit | number/string | 数量与单位（若有） |