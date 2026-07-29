# ABA 搜索词隐藏场景挖掘

从亚马逊 ABA（品牌分析）全年搜索词排名数据里，系统性挖掘珠宝类目**团队未主动投放的隐藏场景需求**（如 sobriety / cross / 身体珠宝 / charm 潮流…）。单文件 Python + pandas，无需数据库。

- 数据：美国站 2025 全年 12 个月，每月约 20 万行，共 **41.4 万**去重搜索词。
- 定位：**两台引擎并行** —— 归纳发现（从数据长出场景）+ 假设验证（拿猜想去数据对答案），互补。

---

## 1. 快速开始

```bash
pip install pandas pyarrow
python3 analyze.py            # 跑完 Phase 0-6，约 1-2 分钟，产出全写入 output/
```

跑完后先读 `output/REPORT.md`（总报告），再按需看各清单。`output/master_wide.parquet` 是主表缓存（脚本会重建，已 gitignore）。

---

## 2. 数据要求

- 12 个 CSV 放在**仓库根目录**，文件名含月份缩写（如 `us_search_terms_jan_2025.csv`，`sept` 为 4 字母）。
- 每文件两列（按**列位置**读，表头名可中可英）：第 1 列 = 排名（越小越热），第 2 列 = 搜索词。
- 脚本自动处理：**混合编码**（UTF-8-BOM / GB18030 逐文件探测）、多余列（只取前两列）、月份映射并打印确认。
- 换新一批数据：替换根目录 CSV，重跑即可；命名或列数不同时脚本会先打印映射供你核对。

---

## 3. 方法论：6 个 Phase

| Phase | 名称 | 干什么 | 引擎 |
|---|---|---|---|
| 0 | 校验清洗 | 探测编码、映射月份、清洗去重 | — |
| 1 | 构建主表 | 长表→宽表，加派生列，存 parquet | — |
| 2 | 词的生死簿 | 新入榜 / 掉榜 / 间歇词 | 归纳 |
| 3 | 排名轨迹 | 持续向好 / 季节 spike / 场景日历 | 归纳 |
| 4 | 结构挖掘 | 4A gift 结构、4B 纪念标记、4C 词族滚雪球、4D 品类画像 | 归纳 |
| 5 | 假设验证 | 拿 `HYPOTHESIS_DICT` 场景词典去全量表核对 | 验证 |
| 6 | **场景发现** | 在珠宝子集里挖词典外的隐藏场景，分簇 | 归纳（主发现引擎）|

**发现 → 验证 闭环**：Phase 6 挖出的新场景 → 回填 `HYPOTHESIS_DICT` → 下轮 Phase 5/4C 自动验证扩展 → 再发现更边缘的。可反复迭代。

---

## 4. 产出清单（`output/`）

所有 CSV 为 `utf-8-sig`，Excel 直接打开不乱码。

| 文件 | 内容 | 怎么用 |
|---|---|---|
| **`REPORT.md`** | 总报告：场景发现置顶、各 Phase 摘要、机会词候选、假设空白区、逐主题解读 | **先读这个** |
| **`candidates.csv`** | 机会词候选合并清单（按 `reasons` 分层） | 动手清单，见 §6 配方 B |
| **`06_discovery.md`** / `06_discovered_scenes.csv` | 珠宝场景发现，按 11 簇归类，★=词典外 | 找未知场景，见 §6 配方 C |
| `00_data_quality.md` | 每月清洗前后行数对照 | 核对数据完整性 |
| `02_new_entrants / dropouts / intermittent[_category].csv` | 生死簿三清单（全量 + 品类版） | 新需求崛起 / 衰退 / 季节 |
| `03_trend_up[_category].csv` | 排名持续向好的词 | 增长型机会 |
| `03_seasonal_spike[_category].csv` | 某月排名冲高的季节词 | 季节备货 |
| `03_spike_calendar.md` | 逐月 spike 高频 token | 场景日历 |
| `04a_gift_scenarios_full.csv` | `gift for X` / `X gift` 的 X 聚合 | 人工扫，找陌生送礼场景 |
| `04b_commemoration_scenarios.csv` | 纪念标记词旁的"被纪念对象" | 纪念类场景 |
| `04c_bare_scenario_terms[_cap150].csv` | 裸场景词（无 gift/标记/品类根） | 验证过场景的结构外变体 |
| `04c_term_families[_cap150].csv` | 词族全成员 + 结构标记 | 回溯一个场景的整族 |
| `04d_modifiers_category.csv` / `04d_gift_recipients_category.csv` | 珠宝词的修饰语 / 收件人画像 | 珠宝正被送给谁 |
| `04e_blindspot_category_cooccur.csv` | 词典外 token 的品类共现度 | 陌生场景优先级排序 |
| `05_hypothesis_hits.csv` / `05_hypothesis_summary.md` | 假设词典命中明细 / 逐主题汇总 | 验证已知方向 |

> `_category` 后缀 = 只保留珠宝品类词的过滤版；`_cap150` = Phase 4C 更宽档位对照。

---

## 5. 怎么看：5 个核心指标

看任何一个词，用这 5 个字段判断：

| 字段 | 含义 | 用法 |
|---|---|---|
| `best_rank` | 全年最热排名（越小越热） | 判断词有多大 |
| `median_rank` | 全年中位排名 | 和 best 对比：都好=常青；best 好 median 差=季节/偶发 |
| `months_present` | 在榜月数 | 12=常青，1-4=间歇/季节 |
| `trend_ratio` | 末3月÷首3月排名 | **<1 在涨**（越小越猛），>1 衰退，空=在榜不足6月 |
| `is_category` | 是否珠宝品类词 | True=已被珠宝搜索验证 |
| `months_on_list` | 在榜月份列表 | 看季节形态（单峰/双峰）|

---

## 6. 怎么分析：三个配方

**配方 A — 验证已知场景**：读 `05_hypothesis_summary.md`，每主题看 ①命中量 ②**品类命中数**（有=已被珠宝验证）③月份分布（季节）。
> ⚠️ 别信主题的"命中总数"——广词（recovery/football/warrior）会被无关品类灌水。**第一动作永远是按 `matched_keyword` 拆开、读实际命中词**，或直接看 `is_category` 列。

**配方 B — 挑马上能投的词**：打开 `candidates.csv`，按 `reasons` 分层：

| reasons | 价值 |
|---|---|
| `Phase5命中×品类` | 已验证需求（场景×珠宝真实搜索），可直接投 |
| `Phase5命中×趋势向好` | 已知场景 + 正在涨，优先 |
| `裸场景词×优质词族` | 结构外的场景变体 |
| `品类新入榜` / `品类季节spike` | 品类内新词/季节词，量大，需用指标二次筛 |

**配方 C — 找未知场景**：读 `06_discovery.md`，看每簇 ★（词典外）场景；再用 `04e_blindspot_category_cooccur.csv` 按品类共现排优先级。发现值得跟进的，回填词典（见 §8）。

---

## 7. 可调参数（`analyze.py` 顶部集中定义）

| 参数 | 默认 | 作用 |
|---|---|---|
| `CATEGORY_ROOTS` | 全套珠宝词根 | 品类判定；**换产品线时增删这里**（复数自动兼容）|
| `CATEGORY_BLACKLIST_PATTERNS` | Ring 品牌/binder/LOTR… | 词边界也挡不住的语义误伤，命中即剔 |
| `HYPOTHESIS_DICT` | 19 个场景主题 | Phase 5 验证词典；`word`=精确，`word*`=前缀，多词=短语 |
| `SEED_MAX_FAMILY_SIZE` | 60 | 4C 词族上限，越大召回越高噪音越多（另出 `_cap150` 对照）|
| `SPIKE_CANDIDATE_MIN_MEDIAN_RANK` | 5000 | 季节 spike 候选门槛，剔除常青头部词 |
| `SCENE_MIN_TERMS` | 3 | Phase 6 一个场景至少出现在 N 个品类词里 |
| `DISCOVERY_SKIP` / `DISCOVERY_CLUSTERS` | 见文件 | Phase 6 去噪词表 / 场景分簇词表 |
| `RELIABLE_RANK_CEILING` | 100000 | 排名变化判定的可信门槛，过滤尾部噪音 |

---

## 8. 闭环怎么迭代

1. 跑一轮，读 `06_discovery.md` 末尾 / `REPORT.md` 顶部的"**建议加入词典**"清单。
2. 挑真实场景，编成新主题加进 `analyze.py` 的 `HYPOTHESIS_DICT`。
   - **先小测噪音**：珠宝已附着型场景（cross/nose）在全量表匹配会带语义噪音，加进 `JEWELRY_ATTACHED_THEMES` 集合，其非品类趋势词就不会污染候选。
   - 零品类命中的词（前 20 万里没有对应珠宝词）验证不出，别加。
3. 重跑。Phase 5 会验证新主题、Phase 4C 会扩展成词族、Phase 6 的"词典外"数会下降（场景毕业成假设）。
4. 重复，每轮触及更边缘的场景。

---

## 9. 已知边界与坑（用之前务必知道）

- **语义歧义**：词边界匹配挡不住 `warrior`（游戏）、`cross`（crossfit）、`football`（球赛）这类。**认准 `is_category` 列**，输出清单人工抽查。
- **两种"隐藏"**：
  - *已附着珠宝的*（cross / nose / croc charm）—— Phase 6 能挖，直接可投。
  - *地板之下的*（sobriety 这类小众情感场景）—— 在 ABA 前 20 万里几乎不成词，**本工具照不到**，需靠你的店铺销售数据 / Etsy / 竞品验证。数据里"查无此人" ≠ 没需求。
- **候选偏 spike/新入榜**：`品类新入榜`+`品类季节spike` 占候选大头，别全投，用 `trend_ratio`+`best_rank` 二次筛；真隐藏信号看 `裸场景词×优质词族` 和 `Phase5命中×趋势向好`。
- **Phase 6 分簇是关键词粗分类**：`未分类` 桶里还有款式/属性待人工归，簇归属偶有错放（如 "dog mom" 落到动物簇），当 triage 线索用、别当定论。
- **尾部抖动**：`best_rank > 10 万` 的排名变化不可信，涉及轨迹的判定已用 `RELIABLE_RANK_CEILING` 挡掉。
- **少量残留噪音**：`bogg bag`（手提袋）、`lucky charms`（麦片）、`basketball hoops`（因"hoops"词根误判）等偶有混入，`is_category=False` 一眼可辨。

---

## 10. 当前一轮产出规模（参考）

- 唯一搜索词 414,489；品类词 5,146（1.24%）
- Phase 5 命中 8,450 条（品类命中 687）
- Phase 4C 词族 56 个 / 裸场景词 589（cap150 对照：69 / 1,466）
- Phase 6 候选场景 325 个，词典外 238，覆盖 11 簇
- 机会词候选 2,123 个
