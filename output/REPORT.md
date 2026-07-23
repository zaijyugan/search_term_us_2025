# ABA 搜索词隐藏需求挖掘 — 分析报告

生成时间：2026-07-23 05:51:58｜数据：美国站 ABA 2025 全年 12 月

## 1. 数据概况

- 月度原始行合计 **2,400,690** → 清洗后 **2,400,688**（损耗 2，0.000%）
- 跨月去重唯一搜索词 **414,489**；其中品类词 **5,146**（1.24%）
- 全年 12 月覆盖，编码混合（10 UTF-8-BOM + 2 GB18030），详见 `00_data_quality.md`

## 2. 各 Phase 核心发现

- **Phase 2 生死簿**：新入榜 500（品类 500）、掉榜 500（品类 500）、间歇 500（品类 500）
- **Phase 3 轨迹**：合格词 139,591；seasonal spike 涉及 38907 词，详见 `03_spike_calendar.md`
- **Phase 4A gift**：X 6,232 个｜**4B 纪念标记**：被纪念 token 232 个｜**4C 词族**：种子 30，裸场景词 **437**
- **Phase 5 假设验证**：命中去重词 2,183，品类命中 129，详见 `05_hypothesis_summary.md`

### 4C 裸场景词 top 10（无 gift / 无标记 / 无品类根的隐藏需求）

| term | best_rank | present | trend | seeds |
|---|--:|--:|--:|---|
| divorced sister | 363 | 7 | 61.69 | divorce* |
| divorce in the black tyler perry | 1469 | 12 | 8.34 | divorce* |
| breast cancer awareness accessories | 1589 | 12 | 0.79 | awareness |
| the perfect divorce jeneva rose | 2026 | 9 | 2.02 | divorce* |
| friendship | 2115 | 9 | 5.44 | friendship |
| breast cancer awareness shirt | 2297 | 3 | — | awareness |
| autism awareness shirt | 2443 | 6 | 44.14 | awareness |
| the perfect divorce | 3197 | 12 | 0.38 | divorce* |
| the divorce insurance | 3445 | 6 | 3.88 | divorce* |
| the saint | 5311 | 12 | 2.00 | saint |

## 3. 机会词候选合并清单

满足任一条件即入选（Phase5命中×品类 / Phase5命中×趋势<0.7 / 品类新入榜 / 品类季节spike〔median_rank≥5000，剔除常青头部词〕 / 裸场景词×优质词族），去重后按 best_rank 排序。完整表见 `candidates.csv`。

共 **1515** 个候选。top 20：

| term | best_rank | present | trend | 品类 | 入选理由 |
|---|--:|--:|--:|:--:|---|
| divorced sister | 363 | 7 | 61.69 |  | 裸场景词×优质词族 |
| graduation gifts for her | 983 | 12 | 0.55 |  | Phase5命中×趋势向好 |
| tiffany & co jewelry | 1001 | 10 | 1.05 | ✓ | 品类季节spike |
| christmas earrings | 1210 | 6 | 0.02 | ✓ | 品类季节spike；品类新入榜 |
| ankle bracelets for women | 1439 | 12 | 1.67 | ✓ | 品类季节spike |
| divorce in the black tyler perry | 1469 | 12 | 8.34 |  | 裸场景词×优质词族 |
| breast cancer awareness accessories | 1589 | 12 | 0.79 |  | 裸场景词×优质词族 |
| gold necklace | 1893 | 12 | 0.33 | ✓ | 品类季节spike |
| christmas earrings for women | 1900 | 4 | — | ✓ | 品类新入榜 |
| the perfect divorce jeneva rose | 2026 | 9 | 2.02 |  | 裸场景词×优质词族 |
| friendship | 2115 | 9 | 5.44 |  | 裸场景词×优质词族 |
| women's jewelry | 2259 | 12 | 2.35 | ✓ | 品类季节spike |
| breast cancer awareness shirt | 2297 | 3 | — |  | 裸场景词×优质词族 |
| autism awareness shirt | 2443 | 6 | 44.14 |  | 裸场景词×优质词族 |
| lucky charms marshmallows only | 2586 | 12 | 3.75 | ✓ | 品类季节spike |
| travel jewelry case | 2592 | 12 | 0.50 | ✓ | 品类季节spike |
| pandora bracelets for women | 2779 | 12 | 1.01 | ✓ | 品类季节spike |
| engagement rings for women | 3137 | 12 | 1.92 | ✓ | Phase5命中×品类 |
| the perfect divorce | 3197 | 12 | 0.38 |  | Phase5命中×趋势向好；裸场景词×优质词族 |
| mosquito repellent bracelets | 3316 | 12 | 1.40 | ✓ | 品类季节spike |

## 4. 假设空白区（人工审阅重点）

以下 4A/4B 条目词数靠前，但**不落在 HYPOTHESIS_DICT 任何主题**内——最可能藏着团队陌生的新场景（4C 已收窄为词典场景的自动扩展，新场景发现主要靠此处人工审阅）。

**4A gift 场景 X（词典外，按词数）：** women(13029), men(4785), kids(2525), girls(1343), adults(1325), dogs(794), christmas(705), boys(662), home(368), car(331), bedroom(317), birthday(264), outside(261), living room(224), face(224), christmas tree(222), woman(209), cats(198), classroom(195), teens(194), toddlers(187), school(186), baby(174), bathroom(163), wall(161)

**4B 被纪念对象（词典外，按词数）：** for(56), gifts(43), 50th(15), of(13), baby(12), 250th(10), decorations(10), hat(10), gift(9), card(9), cards(9), wedding(8), the(8), sleep(8), 25th(7), blanket(7), dog(7), loss(7), book(6), ps5(6), 30th(6), happy(6), shirt(5), princess(5), pet(5)

**4C 已验证场景的裸变体产出 top（种子 → 裸场景词数，供优先跟进）：** awareness(52), prayer(52), saint(39), faith(36), ashes(34), divorce*(31), firefighter(28), retirement(25), friendship(19), police officer(16), quincea*(15), baptism(14), mental health(14), graduate(12), sweet 16(9), matching couple*(8), long distance(7), sympathy(6), purity(5), evil eye(4)

### 4.1 空白区 × 品类共现（优先级排序）

词典外 token 与品类词根的共现越高，越说明这个陌生场景已在珠宝语境里被搜索，最该优先补投。完整表见 `04e_blindspot_category_cooccur.csv`。

| token | 来源 | 品类共现词数 | 占比 | 品类最优rank | 代表品类词 |
|---|:--:|--:|--:|--:|---|
| box | 4B | 82 | 4% | 330 | jewelry box | jewelry box for girls | ring box |
| mens | 4A | 63 | 2% | 4467 | mens bracelet | mens rings | mens jewelry |
| jewelry making | 4A | 56 | 100% | 5620 | jewelry making supplies | beads for jewelry making | jewelry making kit |
| wedding | 4A | 43 | 6% | 6940 | wedding rings for women | wedding ring | womens silicone wedding ring |
| holder | 4B | 34 | 2% | 4645 | earring holder organizer | necklace holder | ring holder |
| womens | 4A | 33 | 1% | 14202 | womens earrings | womens jewelry | womens bracelets |
| travel | 4A | 27 | 2% | 2592 | travel jewelry case | travel jewelry organizer | mini travel jewelry bag |
| hair | 4A | 21 | 0% | 8341 | hair jewelry | gold hair cuffs | hair charms |
| costume | 4B | 20 | 0% | 15374 | costume jewelry | costume jewelry for women | ring master costume female |
| couples | 4A | 19 | 7% | 6532 | couples bracelets | matching bracelets for couples | forever bracelets for couples |
| 2025 | 4B | 18 | 1% | 23299 | jewelry advent calendar 2025 | graduation necklace class of 2025 | graduation bracelet 2025 |
| back | 4B | 17 | 2% | 3975 | flat back earrings | flat back earrings for women | flat back earrings hypoallergenic |
| book | 4B | 13 | 0% | 47008 | the seven rings nora roberts book 3 | my little star book necklace for daughter | book buddies slap bracelets |
| boxes | 4B | 12 | 2% | 5167 | jewelry boxes for women | jewelry boxes | jewelry gift boxes |
| star | 4B | 12 | 2% | 35129 | star earrings | star necklace | my little star book necklace for daughter |
| girl | 4A | 12 | 1% | 41126 | little girl jewelry | little girl jewelry box | little girl earrings |
| cat | 4B | 12 | 1% | 36213 | cat earrings | cat necklace | cat ring holder |
| tree | 4A | 12 | 0% | 40714 | christmas tree earrings | christmas tree earrings for women | tree of life necklace |
| valentine | 4A | 11 | 2% | 19903 | valentine earrings for women | valentine earrings | valentine nail charms |
| dog | 4A | 11 | 0% | 39933 | dog chain | dog chain for yard | dog necklace |

### 4.2 Phase 4C 族上限档位对照

- 默认档 族上限=60：裸场景词 **437**（`04c_bare_scenario_terms.csv`）
- 对照档 族上限=150：裸场景词 **858**（`04c_bare_scenario_terms_cap150.csv`），比默认档多 421 词
- 放宽到 150 才纳入的场景种子：anxiety, best friend*, communion, engagement, memorial, military, nurse, recovery
- 对照档新增裸词 best_rank top 10：nurse jackie(3299); nurse costume(3830); thunder shirt for dogs anxiety(4124); gas masks survival nuclear and chemical military grade(6285); nurse essentials(7376); nurse costume woman(8213); nurse accessories for work(8407); byoma hydrating recovery oil(8439); anxiety relief items(8617); communion cups and wafer set(9465)

## 5. 候选主题解读

### 戒断康复（命中 99，品类 0）

- 戒酒/戒瘾里程碑送礼，9 月 Recovery Month 常见季节峰；sober anniversary/milestone 是核心。
- 在榜高峰月：2025-03(68), 2025-04(63), 2025-06(61)
- 建议验证：挑 best_rank 靠前且 is_category=True 的组合词做小额广告测试，观察是否可低成本承接该场景需求。

### 疾病康复（命中 99，品类 4）

- 癌症幸存者/抗癌纪念，10 月乳腺癌关注月放量；survivor/warrior 需人工排除游戏歧义。
- 在榜高峰月：2025-10(52), 2025-09(43), 2025-03(40)
- 建议验证：挑 best_rank 靠前且 is_category=True 的组合词做小额广告测试，观察是否可低成本承接该场景需求。

### 人生重启（命中 42，品类 0）

- 离婚/分手后重启，fresh start / new chapter 送己或送友。
- 在榜高峰月：2025-06(27), 2025-07(25), 2025-03(22)
- 建议验证：挑 best_rank 靠前且 is_category=True 的组合词做小额广告测试，观察是否可低成本承接该场景需求。

### 成就节点（命中 756，品类 16）

- 毕业/退休/升职/马拉松完赛，5-6 月毕业季与赛事季为峰。
- 在榜高峰月：2025-05(723), 2025-04(332), 2025-06(258)
- 建议验证：挑 best_rank 靠前且 is_category=True 的组合词做小额广告测试，观察是否可低成本承接该场景需求。

### 军警职业（命中 262，品类 0）

- 退伍/部署/护士/消防等职业身份礼，父亲节与退伍纪念日相关。
- 在榜高峰月：2025-10(149), 2025-05(119), 2025-09(114)
- 建议验证：挑 best_rank 靠前且 is_category=True 的组合词做小额广告测试，观察是否可低成本承接该场景需求。

### 纪念哀悼（命中 160，品类 15）

- 逝者纪念/骨灰/指纹首饰，无明显季节，常年稳定刚需。
- 在榜高峰月：2025-05(111), 2025-02(95), 2025-03(88)
- 建议验证：挑 best_rank 靠前且 is_category=True 的组合词做小额广告测试，观察是否可低成本承接该场景需求。

### 信仰精神（命中 345，品类 16）

- 护佑/守护天使/evil eye 等信仰符号。
- 在榜高峰月：2025-06(181), 2025-03(175), 2025-04(166)
- 建议验证：挑 best_rank 靠前且 is_category=True 的组合词做小额广告测试，观察是否可低成本承接该场景需求。

### 关系联结（命中 138，品类 28）

- 异地/情侣对戒/母女父子/闺蜜，节日与婚礼季相关。
- 在榜高峰月：2025-12(88), 2025-02(64), 2025-11(59)
- 建议验证：挑 best_rank 靠前且 is_category=True 的组合词做小额广告测试，观察是否可低成本承接该场景需求。

### 心理健康（命中 92，品类 4）

- 焦虑/心理健康/分号（semicolon）符号，鼓励与陪伴表达。
- 在榜高峰月：2025-01(48), 2025-04(45), 2025-02(41)
- 建议验证：挑 best_rank 靠前且 is_category=True 的组合词做小额广告测试，观察是否可低成本承接该场景需求。

### 身份仪式（命中 119，品类 1）

- 成人礼/受洗/坚振/sweet 16 等身份节点。
- 在榜高峰月：2025-04(104), 2025-05(63), 2025-03(58)
- 建议验证：挑 best_rank 靠前且 is_category=True 的组合词做小额广告测试，观察是否可低成本承接该场景需求。

### 承诺誓约（命中 80，品类 43）

- 承诺戒指/守贞/订婚/重申誓言。
- 在榜高峰月：2025-02(50), 2025-12(49), 2025-01(47)
- 建议验证：挑 best_rank 靠前且 is_category=True 的组合词做小额广告测试，观察是否可低成本承接该场景需求。


---

_方法论：Phase 2/3/4 为无假设归纳发现，Phase 5 为假设验证；词边界匹配无法完全排除语义歧义（如 warrior 可能来自游戏），输出清单需人工抽查。拼写变体/同义词未处理，召回不完整。_
