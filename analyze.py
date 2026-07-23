#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ABA 搜索词隐藏需求挖掘 — 分析脚本
按 ANALYSIS_SPEC.md 的 Phase 0 → 5 顺序执行。

当前实现进度：Phase 0（数据校验与清洗）、Phase 1（构建主表）。
后续 Phase 2-5 在此脚本上继续扩展。

用法：
    python3 analyze.py            # 跑当前已实现的 Phase
所有输出写入 output/ 目录。
"""

import os
import re
import glob
import sys
from datetime import datetime

import pandas as pd
import numpy as np

# =============================================================================
# 可调参数（集中定义）
# =============================================================================

# 品类词根：用于筛选品类相关子集。匹配一律用词边界正则（\broot\b），不用裸子串。
# 决策：使用全量珠宝词根照跑（美国站珠宝类目）。
CATEGORY_ROOTS = [
    "jewelry", "jewellery",
    "necklace", "pendant", "chain", "choker", "locket",
    "bracelet", "bangle", "cuff", "anklet",
    "ring", "rings", "earring", "earrings", "studs", "hoops",
    "brooch", "charm", "charms", "birthstone",
]

# 已知语义误伤（词边界也挡不住的），命中后剔除：
CATEGORY_BLACKLIST_PATTERNS = [
    r"\bkey ring\b", r"\bonion ring\b", r"\bteething ring\b",
    r"\bring light\b", r"\bring doorbell\b", r"\bnapkin ring\b",
    r"\bcurtain ring\b", r"\bring toss\b", r"\bboxing ring\b",
    # --- ring 品牌/智能硬件/同形词噪音（数据驱动补充，见 Phase 1 品质核查）---
    # Ring 智能家居（摄像头/门铃/照明/警报/传感器/配件）—— 名词一律含可选复数
    r"\bcameras?\b", r"\bdoorbells?\b", r"\bdoor bells?\b",
    r"\bfloodlights?\b", r"\bflood lights?\b", r"\bspotlights?\b",
    r"\bchimes?\b", r"\bpeepholes?\b", r"\bsurveillance\b",
    r"\bstick up cam", r"\bstick-up cam", r"\bring cams?\b", r"\bcar cams?\b",
    r"\bring alarm\b", r"\bbase stations?\b", r"\bsecurity systems?\b",
    r"\bsensors?\b", r"\bring battery\b", r"\bring solar\b", r"\bsolar panels?\b",
    r"\bring (?:outdoor|indoor|wired|wireless)\b",
    r"\bring wifi\b", r"\bring wi-fi\b", r"\bwifi extenders?\b", r"\bwi-fi extenders?\b",
    r"\bring subscription\b",
    # 智能/健康监测戒指（Oura / Ultrahuman / 通用 smart ring），非珠宝
    r"\boura\b", r"ōura", r"\bultrahuman\b", r"\baura ring\b",
    r"\bsmart rings?\b", r"\bring smart\b", r"\bsmart health ring\b",
    r"\bfitness ring\b", r"\bhealth ring\b", r"\btracker ring\b",
    r"\b(?:sleep|fitness|health|activity)\s+trackers?\b",
    # 非珠宝的 ring/rings 同形词（3-ring binder / 糖果 ring pop / LOTR 周边 / 普拉提圈）
    r"\bbinders?\b", r"\bsheet protector", r"\bring pops?\b",
    r"\blord of the rings\b", r"\brings of power\b", r"\bpilates ring\b",
]

# 场景假设词典（Phase 5 用）。
HYPOTHESIS_DICT = {
    "戒断康复": ["sober*", "sobriety", "recovery", "one day at a time", "milestone"],
    "疾病康复": ["survivor", "cancer free", "remission", "warrior", "awareness"],
    "人生重启": ["divorce*", "new beginning*", "fresh start", "new chapter", "breakup"],
    "成就节点": ["graduation", "graduate", "promotion", "retirement", "citizenship",
                 "marathon", "finisher", "first job"],
    "军警职业": ["veteran", "deployment", "military", "police officer", "firefighter",
                 "nurse", "paramedic"],
    "纪念哀悼": ["memorial", "remembrance", "in memory", "cremation", "ashes",
                 "sympathy", "keepsake", "fingerprint"],
    "信仰精神": ["faith", "saint", "prayer", "protection", "evil eye", "hamsa",
                 "guardian angel"],
    "关系联结": ["long distance", "matching couple*", "friendship", "father son",
                 "mother daughter", "best friend*", "soul sister*"],
    "心理健康": ["anxiety", "mental health", "semicolon", "encouragement",
                 "you are enough", "stay strong"],
    "身份仪式": ["quincea*", "bat mitzvah", "bar mitzvah", "baptism", "communion",
                 "confirmation", "sweet 16", "sweet sixteen"],
    "承诺誓约": ["promise ring*", "purity", "commitment", "engagement", "vow renewal"],
}

MODIFIER_PATTERNS = [
    r"\bgifts? for ([a-z]+(?: [a-z]+)?)",   # gift for X（优先级最高，最干净）
    r"\bfor ([a-z]+(?: [a-z]+)?)$",          # 以 for X 结尾
    r"\b([a-z]+) gifts?\b",                  # X gift（graduation gift / sobriety gift）
]

COMMEMORATION_MARKERS = [
    "milestone", "anniversary", "award", "medallion", "token", "keepsake",
    "survivor", "memorial", "remembrance", "tribute", "commemorative",
    "achievement", "celebration", "encouragement", "affirmation",
]

SEED_STOPWORDS = [
    "men", "women", "man", "woman", "him", "her", "his", "hers", "boys", "girls",
    "kids", "adults", "teens", "mom", "dad", "grandma", "grandpa", "husband", "wife",
    "christmas", "birthday", "valentines", "halloween", "easter", "day",
    "small", "large", "mini", "cute", "funny", "unique", "personalized", "custom",
    "cheap", "best", "top", "new", "year", "years", "old",
]
SEED_GENERIC_CUTOFF = 0.005   # 通用词门槛：既约束 token 精确词频，也约束种子前缀词族覆盖面
SEED_MIN_FAMILY_SIZE = 3      # 词族至少 N 个成员才输出
SEED_MAX_FAMILY_SIZE = 60     # 词族上限：真正的小众场景词族小；>N 视为通用词泄漏，剔除（可调，越大召回越高噪音越多）
SEED_MIN_TOKEN_LEN = 4        # 种子最短长度：<4 字符前缀（boo/pre/can/leg…）会误捞海量无关词

NEW_ENTRANT_MIN_ABSENT_MONTHS = 3
SEASONAL_MAX_MONTHS = 4
SPIKE_IMPROVE_RATIO = 0.5
RELIABLE_RANK_CEILING = 100000
TOP_OUTPUT_N = 500

# =============================================================================
# 全局常量
# =============================================================================

OUTPUT_DIR = "output"
MASTER_WIDE_PATH = os.path.join(OUTPUT_DIR, "master_wide.parquet")

# 月份缩写 → 数字。覆盖数据文件里出现的写法（sept 为 4 字母）。
MONTH_ABBR_MAP = {
    "jan": "01", "feb": "02", "mar": "03", "apr": "04",
    "may": "05", "jun": "06", "jul": "07", "aug": "08",
    "sep": "09", "sept": "09", "oct": "10", "nov": "11", "dec": "12",
}

# 逐文件编码探测顺序：数据集内混合了 utf-8-sig 与 gb18030。
ENCODING_CANDIDATES = ["utf-8-sig", "gb18030"]


# =============================================================================
# 工具函数
# =============================================================================

def log(msg):
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def ensure_output_dir():
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def build_category_regex():
    """品类词根 → 单个词边界正则（含可选复数 s/es）；黑名单 → 单个正则。"""
    roots = sorted(set(CATEGORY_ROOTS), key=len, reverse=True)
    # 追加可选复数尾缀，令 necklace 同时命中 necklaces、brooch 命中 brooches
    root_re = re.compile(r"\b(?:" + "|".join(re.escape(r) for r in roots) + r")(?:e?s)?\b")
    black_re = re.compile("|".join(CATEGORY_BLACKLIST_PATTERNS))
    return root_re, black_re


def detect_month(filename):
    """从文件名解析月份，返回 '2025-MM'。"""
    base = os.path.basename(filename).lower()
    # 优先匹配更长的缩写（sept 先于 sep）
    for abbr in sorted(MONTH_ABBR_MAP, key=len, reverse=True):
        if re.search(rf"_{abbr}_", base):
            return f"2025-{MONTH_ABBR_MAP[abbr]}"
    return None


def detect_encoding(path):
    """逐候选编码尝试读取表头，返回第一个能解码的编码。"""
    for enc in ENCODING_CANDIDATES:
        try:
            with open(path, "r", encoding=enc) as fh:
                fh.readline()
            return enc
        except (UnicodeDecodeError, UnicodeError):
            continue
    # 兜底：latin-1 永不报错（数据行为英文 ASCII，安全）
    return "latin-1"


# =============================================================================
# Phase 0 — 数据校验与清洗
# =============================================================================

def phase0_load_and_clean():
    """
    读取全部月度 CSV，按位置取前两列（rank, term），清洗后返回长表 DataFrame
    （列：month, rank, term）以及每月清洗前后统计。
    """
    log("=== Phase 0：数据校验与清洗 ===")
    files = sorted(glob.glob("us_search_terms_*_2025.csv"))
    if not files:
        sys.exit("未找到 us_search_terms_*_2025.csv 数据文件")

    # 文件 → 月份映射，打印确认
    mapping = []
    for f in files:
        m = detect_month(f)
        mapping.append((os.path.basename(f), m))
    log("文件 → 月份映射：")
    for fn, m in sorted(mapping, key=lambda x: x[1] or ""):
        print(f"    {fn:34s} -> {m}")
    months_seen = [m for _, m in mapping]
    assert len(set(months_seen)) == 12, f"月份映射不是 12 个唯一值：{sorted(set(months_seen))}"

    quality_rows = []
    frames = []

    for f in files:
        month = detect_month(f)
        enc = detect_encoding(f)
        # 只取前两列：col0=rank, col1=term（jul 有多余列，usecols 忽略）
        # header=None + skiprows=1：跳过真实表头行，其余按位置读取。
        # （不可与 header=0 同用，否则会把首条数据行当表头吃掉，丢失 rank=1 词）
        df = pd.read_csv(
            f, encoding=enc, header=None, usecols=[0, 1],
            names=["rank", "term"], skiprows=1,
            dtype={0: "string", 1: "string"},
            na_filter=False, low_memory=False,
        )
        raw_rows = len(df)

        # rank 转整数，失败行剔除并计数
        rank_num = pd.to_numeric(df["rank"], errors="coerce")
        bad_rank = int(rank_num.isna().sum())
        df = df.loc[rank_num.notna()].copy()
        df["rank"] = rank_num.loc[rank_num.notna()].astype("int64").values

        # term 清洗：小写、去首尾空格、连续空格合并为一个
        term = df["term"].astype("string").str.lower().str.strip()
        term = term.str.replace(r"\s+", " ", regex=True)
        df["term"] = term

        # 空 term 剔除
        empty_term = int((df["term"] == "").sum() + df["term"].isna().sum())
        df = df.loc[(df["term"] != "") & df["term"].notna()].copy()

        # 同月同 term 保留最小 rank
        before_dedup = len(df)
        df = df.sort_values("rank").drop_duplicates(subset=["term"], keep="first")
        dup_removed = before_dedup - len(df)

        df["month"] = month
        frames.append(df[["month", "rank", "term"]])

        quality_rows.append({
            "month": month,
            "file": os.path.basename(f),
            "encoding": enc,
            "raw_rows": raw_rows,
            "bad_rank_dropped": bad_rank,
            "empty_term_dropped": empty_term,
            "dup_term_dropped": dup_removed,
            "clean_rows": len(df),
            "rank_min": int(df["rank"].min()),
            "rank_max": int(df["rank"].max()),
        })
        log(f"  {month}  enc={enc:9s} raw={raw_rows:>7,} -> clean={len(df):>7,} "
            f"(bad_rank={bad_rank}, empty={empty_term}, dup={dup_removed})")

    long_df = pd.concat(frames, ignore_index=True)
    quality = pd.DataFrame(quality_rows).sort_values("month").reset_index(drop=True)

    write_data_quality_report(quality, long_df)
    log(f"Phase 0 完成：长表 {len(long_df):,} 行，覆盖 {long_df['month'].nunique()} 个月")
    return long_df, quality


def write_data_quality_report(quality, long_df):
    ensure_output_dir()
    path = os.path.join(OUTPUT_DIR, "00_data_quality.md")
    total_raw = int(quality["raw_rows"].sum())
    total_clean = int(quality["clean_rows"].sum())
    total_dropped = total_raw - total_clean
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("# Phase 0 — 数据校验与清洗报告\n\n")
        fh.write(f"生成时间：{datetime.now():%Y-%m-%d %H:%M:%S}\n\n")
        fh.write("## 每月清洗前后行数对照\n\n")
        fh.write("| 月份 | 文件 | 编码 | 原始行 | rank非法 | 空term | 同term重复 | 清洗后 | rank最小 | rank最大 |\n")
        fh.write("|---|---|---|--:|--:|--:|--:|--:|--:|--:|\n")
        for _, r in quality.iterrows():
            fh.write(f"| {r['month']} | {r['file']} | {r['encoding']} | "
                     f"{r['raw_rows']:,} | {r['bad_rank_dropped']:,} | "
                     f"{r['empty_term_dropped']:,} | {r['dup_term_dropped']:,} | "
                     f"{r['clean_rows']:,} | {r['rank_min']:,} | {r['rank_max']:,} |\n")
        fh.write(f"| **合计** | 12 文件 | — | **{total_raw:,}** | "
                 f"**{int(quality['bad_rank_dropped'].sum()):,}** | "
                 f"**{int(quality['empty_term_dropped'].sum()):,}** | "
                 f"**{int(quality['dup_term_dropped'].sum()):,}** | "
                 f"**{total_clean:,}** | — | — |\n\n")
        fh.write(f"**清洗损耗**：{total_dropped:,} 行 "
                 f"（{total_dropped / total_raw * 100:.3f}%），"
                 f"其中重复词 {int(quality['dup_term_dropped'].sum()):,}、"
                 f"rank非法 {int(quality['bad_rank_dropped'].sum()):,}、"
                 f"空term {int(quality['empty_term_dropped'].sum()):,}。\n\n")
        fh.write(f"**唯一搜索词总数**（跨月去重）：{long_df['term'].nunique():,}\n\n")
        fh.write("## 编码说明\n\n")
        fh.write("数据集混合编码：多数文件为 UTF-8-BOM，`jan`/`jul` 为 GB18030；"
                 "脚本逐文件探测。`jul` 文件含多余列，按列位置只取前两列。\n")
    log(f"已写出 {path}")


# =============================================================================
# Phase 1 — 构建主表
# =============================================================================

def phase1_build_master(long_df):
    """
    长表 -> 宽表（行=term，列=各月 rank），附加派生列，保存 parquet。
    """
    log("=== Phase 1：构建主表 ===")
    months = sorted(long_df["month"].unique())

    # 透视为宽表：值 = rank，缺失 = 当月不在前 20 万名
    wide = long_df.pivot(index="term", columns="month", values="rank")
    wide = wide.reindex(columns=months)
    wide.columns = list(months)  # 扁平列名

    rank_matrix = wide[months]

    # 派生列
    wide["months_present"] = rank_matrix.notna().sum(axis=1).astype("int64")
    wide["best_rank"] = rank_matrix.min(axis=1)
    wide["worst_rank"] = rank_matrix.max(axis=1)
    wide["median_rank"] = rank_matrix.median(axis=1)

    # first / last month（在榜的首末月份）
    present_mask = rank_matrix.notna()
    month_idx = {m: i for i, m in enumerate(months)}
    idx_arr = present_mask.values  # bool matrix
    import numpy as np
    col_pos = np.arange(len(months))
    first_pos = np.where(idx_arr, col_pos, np.nan)
    wide["first_month"] = [months[int(v)] for v in np.nanmin(first_pos, axis=1).astype(int)]
    last_pos = np.where(idx_arr, col_pos, np.nan)
    wide["last_month"] = [months[int(v)] for v in np.nanmax(last_pos, axis=1).astype(int)]

    # trend_ratio：在榜 >=6 个月的词，末3在榜月中位数 / 首3在榜月中位数
    wide["trend_ratio"] = _compute_trend_ratio(rank_matrix, months)

    # is_category
    root_re, black_re = build_category_regex()
    terms = wide.index.to_series()
    hit_root = terms.str.contains(root_re, regex=True)
    hit_black = terms.str.contains(black_re, regex=True)
    wide["is_category"] = (hit_root & ~hit_black).values

    wide = wide.reset_index()

    ensure_output_dir()
    wide.to_parquet(MASTER_WIDE_PATH, index=False)
    log(f"已保存宽表 {MASTER_WIDE_PATH}：{len(wide):,} 行 × {wide.shape[1]} 列")

    _print_phase1_summary(wide, months)
    return wide


def _compute_trend_ratio(rank_matrix, months):
    import numpy as np
    vals = rank_matrix.values  # (n_terms, 12), NaN=不在榜
    n = vals.shape[0]
    out = np.full(n, np.nan)
    present_count = np.sum(~np.isnan(vals), axis=1)
    eligible = present_count >= 6
    for i in np.where(eligible)[0]:
        row = vals[i]
        present_vals = row[~np.isnan(row)]  # 按月份顺序排列
        first3 = present_vals[:3]
        last3 = present_vals[-3:]
        denom = np.median(first3)
        if denom > 0:
            out[i] = np.median(last3) / denom
    return out


def _print_phase1_summary(wide, months):
    n = len(wide)
    log(f"  唯一词总数：{n:,}")
    log(f"  is_category=True：{int(wide['is_category'].sum()):,} "
        f"（{wide['is_category'].mean() * 100:.2f}%）")
    dist = wide["months_present"].value_counts().sort_index()
    log("  在榜月份数分布：")
    for k, v in dist.items():
        print(f"      {k:>2} 个月: {v:>8,}")
    n_trend = int(wide["trend_ratio"].notna().sum())
    log(f"  可算 trend_ratio 的词（在榜>=6月）：{n_trend:,}")


# =============================================================================
# 主流程
# =============================================================================

# =============================================================================
# 共享工具：token 索引、结构标记、正则
# =============================================================================

WORD_RE = re.compile(r"[a-z0-9']+")
GIFT_RE = re.compile(r"\bgifts?\b")


def tokenize(term):
    return WORD_RE.findall(term)


def build_marker_regex():
    markers = sorted(set(COMMEMORATION_MARKERS), key=len, reverse=True)
    return re.compile(r"\b(?:" + "|".join(re.escape(m) for m in markers) + r")\b")


def month_list_str(row, months):
    """给定宽表一行，返回在榜月份列表字符串，如 '2025-01;2025-09'。"""
    return ";".join(m for m in months if pd.notna(row[m]))


def prepare_context(wide):
    """
    预计算后续 Phase 复用的结构：
      - months：月份列名列表
      - term_tokens：每行 term 的 token 集合（与 wide 行对齐）
      - token_docfreq：token -> 出现该 token 的唯一词占比
      - wide 上新增布尔列 has_gift / has_marker（is_category 已在 Phase 1 生成）
    """
    log("预计算 token 索引与结构标记 ...")
    months = [c for c in wide.columns if re.fullmatch(r"2025-\d{2}", c)]
    terms = wide["term"].tolist()
    term_tokens = [set(tokenize(t)) for t in terms]

    total = len(terms)
    from collections import Counter
    dfreq = Counter()
    for toks in term_tokens:
        dfreq.update(toks)
    token_docfreq = {tok: cnt / total for tok, cnt in dfreq.items()}

    marker_re = build_marker_regex()
    wide["has_gift"] = wide["term"].str.contains(GIFT_RE, regex=True, na=False).to_numpy()
    wide["has_marker"] = wide["term"].str.contains(marker_re, regex=True, na=False).to_numpy()

    ctx = {
        "months": months,
        "term_tokens": term_tokens,
        "token_docfreq": token_docfreq,
        "total_terms": total,
        "marker_re": marker_re,
    }
    log(f"  has_gift={int(wide['has_gift'].sum()):,}  "
        f"has_marker={int(wide['has_marker'].sum()):,}  "
        f"唯一 token={len(token_docfreq):,}")
    return ctx


def write_csv(df, name):
    ensure_output_dir()
    path = os.path.join(OUTPUT_DIR, name)
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return path, len(df)


def top3_reps(terms_series):
    """取 best_rank 最好的最多 3 个代表词（terms_series 已按 best_rank 升序）。"""
    return " | ".join(terms_series.head(3).tolist())


# =============================================================================
# Phase 2 — 词的生死簿
# =============================================================================

def _rank_matrix(wide, months):
    return wide[months].to_numpy()


def phase2_lifecycle(wide, ctx):
    import numpy as np
    log("=== Phase 2：词的生死簿 ===")
    months = ctx["months"]
    n_absent = NEW_ENTRANT_MIN_ABSENT_MONTHS
    mat = _rank_matrix(wide, months)
    present = ~np.isnan(mat)            # (n_terms, 12) bool
    n = present.shape[0]
    col = np.arange(len(months))

    # --- 新入榜：前 n_absent 月全不在榜，之后首次入榜且入榜后连续在榜到年底 ---
    absent_head = ~present[:, :n_absent].any(axis=1)          # 前 n 月都缺
    first_idx = np.where(present.any(axis=1),
                         np.argmax(present, axis=1), -1)       # 首次在榜列
    # 入榜后连续在榜：从 first_idx 到末尾全部在榜
    def continuous_after(i, fi):
        if fi < 0:
            return False
        return present[i, fi:].all()
    cont = np.array([continuous_after(i, first_idx[i]) for i in range(n)])
    new_entrant = absent_head & (first_idx >= n_absent) & cont

    # --- 掉榜：上半年在榜，下半年出现连续 >=3 个月缺榜 ---
    h1_present = present[:, :6].any(axis=1)
    def longest_absent_run(i):
        run = best = 0
        for j in range(6, len(months)):
            if not present[i, j]:
                run += 1
                best = max(best, run)
            else:
                run = 0
        return best
    h2_gap = np.array([longest_absent_run(i) >= 3 for i in range(n)])
    dropout = h1_present & h2_gap

    # --- 间歇词：months_present <= SEASONAL_MAX_MONTHS ---
    intermittent = wide["months_present"].to_numpy() <= SEASONAL_MAX_MONTHS

    base_cols = ["term", "best_rank", "worst_rank", "median_rank",
                 "months_present", "first_month", "last_month",
                 "trend_ratio", "is_category"]

    def emit(mask, name, add_monthlist=False):
        sub = wide.loc[mask, base_cols].copy()
        if add_monthlist:
            ml = wide.loc[mask].apply(lambda r: month_list_str(r, months), axis=1)
            sub["months_on_list"] = ml.to_numpy()
        sub = sub.sort_values("best_rank").head(TOP_OUTPUT_N)
        # 全量版
        p, c = write_csv(sub, f"{name}.csv")
        # 品类过滤版
        subcat = wide.loc[mask & wide["is_category"].fillna(False).to_numpy(), base_cols].copy()
        if add_monthlist:
            mlc = wide.loc[mask & wide["is_category"].fillna(False).to_numpy()].apply(
                lambda r: month_list_str(r, months), axis=1)
            subcat["months_on_list"] = mlc.to_numpy()
        subcat = subcat.sort_values("best_rank").head(TOP_OUTPUT_N)
        pc, cc = write_csv(subcat, f"{name}_category.csv")
        log(f"  {name}: 全量 {c} 条 / 品类 {cc} 条")
        return c, cc

    r_new = emit(new_entrant, "02_new_entrants")
    r_drop = emit(dropout, "02_dropouts")
    r_int = emit(intermittent, "02_intermittent", add_monthlist=True)

    return {
        "new_entrant_mask": new_entrant,
        "dropout_mask": dropout,
        "intermittent_mask": intermittent,
        "counts": {"new_entrants": r_new, "dropouts": r_drop, "intermittent": r_int},
    }


# =============================================================================
# Phase 3 — 排名轨迹分析
# =============================================================================

def phase3_trajectory(wide, ctx):
    import numpy as np
    log("=== Phase 3：排名轨迹分析 ===")
    months = ctx["months"]
    eligible = (wide["months_present"] >= 6) & (wide["best_rank"] < RELIABLE_RANK_CEILING)
    log(f"  合格词（在榜>=6月 且 best_rank<{RELIABLE_RANK_CEILING:,}）：{int(eligible.sum()):,}")

    base_cols = ["term", "best_rank", "median_rank", "months_present",
                 "trend_ratio", "first_month", "last_month", "is_category"]

    # --- 3.1 trend_up：trend_ratio 升序 ---
    tu = wide.loc[eligible & wide["trend_ratio"].notna(), base_cols].copy()
    tu = tu.sort_values("trend_ratio")
    write_csv(tu.head(TOP_OUTPUT_N), "03_trend_up.csv")
    write_csv(tu[tu["is_category"].fillna(False)].head(TOP_OUTPUT_N),
              "03_trend_up_category.csv")
    log(f"  03_trend_up: 全量 {min(len(tu),TOP_OUTPUT_N)} / 品类 "
        f"{min(int(tu['is_category'].fillna(False).sum()),TOP_OUTPUT_N)}")

    # --- 3.2 seasonal_spike：某月 rank <= (1-SPIKE_IMPROVE_RATIO)*median_rank ---
    elig_idx = np.where(eligible.to_numpy())[0]
    mat = _rank_matrix(wide, months)
    med = wide["median_rank"].to_numpy()
    thresh = (1.0 - SPIKE_IMPROVE_RATIO) * med
    spike_rows = []
    for i in elig_idx:
        row = mat[i]
        for j, m in enumerate(months):
            r = row[j]
            if not np.isnan(r) and r <= thresh[i]:
                spike_rows.append({
                    "term": wide.iat[i, 0],
                    "spike_month": m,
                    "spike_rank": int(r),
                    "median_rank": float(med[i]),
                    "improve_ratio": round((med[i] - r) / med[i], 3),
                    "is_category": bool(wide["is_category"].iat[i]),
                })
    spike_df = pd.DataFrame(spike_rows)
    if len(spike_df):
        spike_df = spike_df.sort_values("spike_rank")
        write_csv(spike_df.head(TOP_OUTPUT_N), "03_seasonal_spike.csv")
        write_csv(spike_df[spike_df["is_category"]].head(TOP_OUTPUT_N),
                  "03_seasonal_spike_category.csv")
        n_spike_terms = spike_df["term"].nunique()
    else:
        write_csv(pd.DataFrame(columns=["term", "spike_month", "spike_rank",
                                        "median_rank", "improve_ratio", "is_category"]),
                  "03_seasonal_spike.csv")
        write_csv(pd.DataFrame(columns=["term", "spike_month", "spike_rank",
                                        "median_rank", "improve_ratio", "is_category"]),
                  "03_seasonal_spike_category.csv")
        n_spike_terms = 0
    log(f"  03_seasonal_spike: {len(spike_df)} 条 spike 记录，涉及 {n_spike_terms} 词")

    # --- 3.3 spike_calendar：逐月 spike 词高频 token top30 ---
    write_spike_calendar(spike_df, months)

    return {"spike_df": spike_df, "trend_up_df": tu, "eligible_mask": eligible}


def write_spike_calendar(spike_df, months):
    from collections import Counter
    stop = set(SEED_STOPWORDS)
    path = os.path.join(OUTPUT_DIR, "03_spike_calendar.md")
    hint = {
        "2025-01": "Dry January / 新年决心", "2025-02": "情人节",
        "2025-03": "—", "2025-04": "—",
        "2025-05": "母亲节 + 毕业季", "2025-06": "父亲节 + 婚礼季",
        "2025-07": "—", "2025-08": "开学季",
        "2025-09": "Recovery Month", "2025-10": "乳腺癌关注月",
        "2025-11": "礼品季（黑五）", "2025-12": "礼品季（圣诞）",
    }
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("# Phase 3 — Spike 场景日历\n\n")
        fh.write("每月排名 spike 词的高频 token（剔除停用词）top 30，用于人工比对场景日历。\n\n")
        if not len(spike_df):
            fh.write("_本期无 spike 词。_\n")
            log(f"已写出 {path}（空）")
            return
        for m in months:
            terms = spike_df.loc[spike_df["spike_month"] == m, "term"].tolist()
            cnt = Counter()
            for t in terms:
                cnt.update(tok for tok in set(tokenize(t)) if tok not in stop and len(tok) > 1)
            top = cnt.most_common(30)
            fh.write(f"## {m}  ·  {hint.get(m,'—')}  （spike 词 {len(terms)}）\n\n")
            if top:
                fh.write(", ".join(f"{tok}({c})" for tok, c in top) + "\n\n")
            else:
                fh.write("_无_\n\n")
    log(f"已写出 {path}")


# =============================================================================
# Phase 4 — 结构挖掘 + 词族扩展
# =============================================================================

def _extract_modifiers(term, patterns):
    """对单个 term 应用全部 MODIFIER_PATTERNS，返回去重后的 X 集合。"""
    xs = set()
    for pat in patterns:
        for mobj in re.finditer(pat, term):
            x = mobj.group(1).strip()
            if x:
                xs.add(x)
    return xs


def _aggregate_x(pairs, wide_indexed):
    """
    pairs: list of (x, term_row_index)。按 x 聚合：词数、best_rank 中位数、代表词3。
    wide_indexed: wide DataFrame（RangeIndex），用于取 best_rank/term。
    """
    from collections import defaultdict
    buckets = defaultdict(list)
    for x, idx in pairs:
        buckets[x].append(idx)
    rows = []
    best_rank = wide_indexed["best_rank"].to_numpy()
    terms = wide_indexed["term"].to_numpy()
    for x, idxs in buckets.items():
        idxs_u = list(set(idxs))
        brs = best_rank[idxs_u]
        srt = np.argsort(brs)
        reps = [terms[idxs_u[k]] for k in srt[:3]]
        rows.append({
            "x": x,
            "n_terms": len(idxs_u),
            "best_rank_median": float(np.median(brs)),
            "best_rank_min": int(np.min(brs)),
            "rep_terms": " | ".join(reps),
        })
    return pd.DataFrame(rows)


def phase4a_gift(wide, ctx):
    log("=== Phase 4A：gift 结构抽取（全量）===")
    pairs = []
    terms = wide["term"].to_numpy()
    for i, t in enumerate(terms):
        for x in _extract_modifiers(t, MODIFIER_PATTERNS):
            pairs.append((x, i))
    agg = _aggregate_x(pairs, wide)
    agg = agg.sort_values("n_terms", ascending=False)
    write_csv(agg.head(TOP_OUTPUT_N), "04a_gift_scenarios_full.csv")
    log(f"  抽出 X {len(agg):,} 个，输出 top {min(len(agg),TOP_OUTPUT_N)}")
    return agg


def phase4b_commemoration(wide, ctx):
    log("=== Phase 4B：纪念标记结构抽取（全量）===")
    marker_re = ctx["marker_re"]
    markers = set(COMMEMORATION_MARKERS)
    stop = set(SEED_STOPWORDS)
    terms = wide["term"].to_numpy()
    best_rank = wide["best_rank"].to_numpy()
    hit_mask = wide["has_marker"].to_numpy()

    from collections import defaultdict
    buckets = defaultdict(list)  # token -> list of row idx
    for i in np.where(hit_mask)[0]:
        toks = tokenize(terms[i])
        # 剥掉标记词本身与停用词，剩余 token 作为被纪念对象候选
        residual = [tok for tok in toks if tok not in markers and tok not in stop]
        for tok in set(residual):
            buckets[tok].append(i)

    rows = []
    for tok, idxs in buckets.items():
        idxs_u = list(set(idxs))
        brs = best_rank[idxs_u]
        srt = np.argsort(brs)
        reps = [terms[idxs_u[k]] for k in srt[:3]]
        rows.append({
            "commemorated_token": tok,
            "n_terms": len(idxs_u),
            "best_rank_median": float(np.median(brs)),
            "best_rank_min": int(np.min(brs)),
            "rep_terms": " | ".join(reps),
        })
    agg = pd.DataFrame(rows).sort_values("n_terms", ascending=False)
    write_csv(agg, "04b_commemoration_scenarios.csv")
    log(f"  命中标记词 {int(hit_mask.sum()):,} 条，被纪念对象 token {len(agg):,} 个")
    return agg


def phase4c_snowball(wide, ctx, gift_agg, comm_agg):
    """
    种子滚雪球 —— 从「已验证的场景词汇」（HYPOTHESIS_DICT 关键词，按短语/前缀/精确语义
    匹配）出发，捞出各场景词族，并抽取族内无结构成员（裸场景词）。

    设计说明（相对 spec 的数据驱动调整，已在 REPORT 中说明）：
      spec 原方案种子池 = 4A gift-X + 4B 被纪念 token + Phase5 场景 token。实测本数据集里
      4A/4B 的残留 token 被通用词（glass/holder/cards…）和影视书名（twilight/tyler perry…）
      主导，前缀滚雪球会淹没出 10 万+ 无关词。故此处只用 Phase5 词典关键词作为高置信场景种子，
      并加两道闸：族规模上限 SEED_MAX_FAMILY_SIZE（小众场景族小）、族内须含结构锚点
      （gift/marker/category 任一，符合 spec「族内几乎总有结构成员」前提）。
      4A/4B 仍作为独立产出与 REPORT「假设空白区」，供人工发现词典外的新场景。
    """
    log("=== Phase 4C：种子滚雪球（词典场景种子）===")
    compiled = _compile_hypothesis()  # {theme: [(kw, regex)]}

    terms = wide["term"]
    best_rank = wide["best_rank"].to_numpy()
    has_gift = wide["has_gift"].to_numpy()
    has_marker = wide["has_marker"].to_numpy()
    is_cat = wide["is_category"].fillna(False).to_numpy()
    months = ctx["months"]

    family_rows = []
    bare_idx_all = set()
    n_family = 0
    n_toobroad = 0
    n_noanchor = 0
    seen_seed = set()
    for theme, lst in compiled.items():
        for kw, rgx in lst:
            if kw in seen_seed:
                continue
            seen_seed.add(kw)
            m = terms.str.contains(rgx, regex=True, na=False).to_numpy()
            idxs = np.where(m)[0]
            if len(idxs) < SEED_MIN_FAMILY_SIZE:
                continue
            if len(idxs) > SEED_MAX_FAMILY_SIZE:   # 通用词泄漏，剔除
                n_toobroad += 1
                continue
            anchor = has_gift[idxs] | has_marker[idxs] | is_cat[idxs]
            if not anchor.any():                   # 全族无结构锚点（spec 已知盲区），跳过
                n_noanchor += 1
                continue
            n_family += 1
            for i in idxs:
                bare = not (has_gift[i] or has_marker[i] or is_cat[i])
                if bare:
                    bare_idx_all.add(i)
                family_rows.append({
                    "seed": kw,
                    "theme": theme,
                    "family_size": len(idxs),
                    "term": terms.iat[i],
                    "best_rank": int(best_rank[i]) if not np.isnan(best_rank[i]) else None,
                    "months_present": int(wide["months_present"].iat[i]),
                    "months_on_list": month_list_str(wide.iloc[i], months),
                    "has_gift": bool(has_gift[i]),
                    "has_marker": bool(has_marker[i]),
                    "is_category": bool(is_cat[i]),
                    "is_bare_scenario": bare,
                })
    fam_df = pd.DataFrame(family_rows)
    if len(fam_df):
        fam_df = fam_df.sort_values(["family_size", "seed", "best_rank"],
                                    ascending=[False, True, True])
    write_csv(fam_df, "04c_term_families.csv")
    log(f"  合格词族 {n_family} 个（过宽剔除 {n_toobroad}，无锚点剔除 {n_noanchor}），"
        f"成员行 {len(fam_df):,}")

    # 裸场景词汇总
    if bare_idx_all:
        bidx = sorted(bare_idx_all)
        bare_df = wide.iloc[bidx][["term", "best_rank", "worst_rank", "median_rank",
                                   "months_present", "first_month", "last_month",
                                   "trend_ratio", "is_category"]].copy()
        seed_map = {}
        theme_map = {}
        for _, r in fam_df[fam_df["is_bare_scenario"]].iterrows():
            seed_map.setdefault(r["term"], set()).add(r["seed"])
            theme_map.setdefault(r["term"], set()).add(r["theme"])
        bare_df["seeds"] = bare_df["term"].map(lambda t: ";".join(sorted(seed_map.get(t, []))))
        bare_df["themes"] = bare_df["term"].map(lambda t: ";".join(sorted(theme_map.get(t, []))))
        bare_df = bare_df.sort_values("best_rank")
    else:
        bare_df = pd.DataFrame(columns=["term", "best_rank", "worst_rank", "median_rank",
                                        "months_present", "first_month", "last_month",
                                        "trend_ratio", "is_category", "seeds", "themes"])
    write_csv(bare_df, "04c_bare_scenario_terms.csv")
    log(f"  裸场景词 {len(bare_df):,}")

    seeds_kept = sorted(set(fam_df["seed"])) if len(fam_df) else []
    return {"families": fam_df, "bare": bare_df, "seeds": seeds_kept}


def phase4d_category(wide, ctx):
    log("=== Phase 4D：品类子集画像 ===")
    cat = wide[wide["is_category"].fillna(False)].reset_index(drop=True)
    # 4A 抽取聚合（品类子集）
    pairs = []
    terms = cat["term"].to_numpy()
    for i, t in enumerate(terms):
        for x in _extract_modifiers(t, MODIFIER_PATTERNS):
            pairs.append((x, i))
    agg = _aggregate_x(pairs, cat).sort_values("n_terms", ascending=False)
    write_csv(agg.head(TOP_OUTPUT_N), "04d_modifiers_category.csv")

    # gift for X 收件人清单（仅 pattern1）
    recip = []
    p1 = MODIFIER_PATTERNS[0]
    for i, t in enumerate(terms):
        for mobj in re.finditer(p1, t):
            recip.append((mobj.group(1).strip(), i))
    recip_agg = _aggregate_x(recip, cat).sort_values("n_terms", ascending=False)
    recip_agg = recip_agg.rename(columns={"x": "gift_recipient"})
    write_csv(recip_agg.head(TOP_OUTPUT_N), "04d_gift_recipients_category.csv")
    log(f"  品类修饰语 X {len(agg):,} 个；gift-for-X 收件人 {len(recip_agg):,} 个")
    return {"modifiers": agg, "recipients": recip_agg}


# =============================================================================
# Phase 5 — 假设词典验证
# =============================================================================

def _compile_hypothesis():
    """把 HYPOTHESIS_DICT 编译为 {theme: [(keyword, regex), ...]}。"""
    compiled = {}
    for theme, kws in HYPOTHESIS_DICT.items():
        lst = []
        for kw in kws:
            if kw.endswith("*"):
                base = kw[:-1].strip()
                parts = base.split()
                pat = r"\b" + r"\s+".join(re.escape(p) for p in parts)
            else:
                parts = kw.split()
                pat = r"\b" + r"\s+".join(re.escape(p) for p in parts) + r"\b"
            lst.append((kw, re.compile(pat)))
        compiled[theme] = lst
    return compiled


def phase5_hypothesis(wide, ctx):
    log("=== Phase 5：假设词典验证（全量）===")
    compiled = _compile_hypothesis()
    terms = wide["term"]
    rows = []
    months = ctx["months"]
    # 逐关键词向量化扫描
    for theme, lst in compiled.items():
        for kw, rgx in lst:
            mask = terms.str.contains(rgx, regex=True, na=False).to_numpy()
            for i in np.where(mask)[0]:
                rows.append({
                    "theme": theme,
                    "matched_keyword": kw,
                    "term": terms.iat[i],
                    "months_present": int(wide["months_present"].iat[i]),
                    "months_on_list": month_list_str(wide.iloc[i], months),
                    "best_rank": int(wide["best_rank"].iat[i]),
                    "trend_ratio": (round(float(wide["trend_ratio"].iat[i]), 3)
                                    if pd.notna(wide["trend_ratio"].iat[i]) else None),
                    "is_category": bool(wide["is_category"].iat[i]),
                })
    hits = pd.DataFrame(rows)
    if len(hits):
        hits = hits.sort_values(["theme", "best_rank"])
    write_csv(hits, "05_hypothesis_hits.csv")

    write_hypothesis_summary(hits)
    n_terms = hits["term"].nunique() if len(hits) else 0
    log(f"  命中 {len(hits):,} 条（去重词 {n_terms:,}），"
        f"品类命中 {int(hits['is_category'].sum()) if len(hits) else 0}")

    # 供 4C 的场景 token：只取「实际命中的词典关键词」基词（干净场景词），
    # 不取命中词的全部 token（后者会把 necklace/silver 等无关附带词混进种子池）
    scene_tokens = set()
    if len(hits):
        for kw in hits["matched_keyword"].unique():
            base = kw[:-1] if kw.endswith("*") else kw
            for tok in tokenize(base.lower()):
                scene_tokens.add(tok)
    return {"hits": hits, "scene_tokens": scene_tokens}


def write_hypothesis_summary(hits):
    path = os.path.join(OUTPUT_DIR, "05_hypothesis_summary.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("# Phase 5 — 假设词典验证汇总\n\n")
        if not len(hits):
            fh.write("_无命中。_\n")
            log(f"已写出 {path}（空）")
            return
        for theme in HYPOTHESIS_DICT:
            sub = hits[hits["theme"] == theme]
            uterms = sub.drop_duplicates("term")
            fh.write(f"## {theme}\n\n")
            fh.write(f"- 命中词数（去重）：**{uterms['term'].nunique()}**；"
                     f"其中品类词 {int(uterms['is_category'].sum())}\n")
            if not len(uterms):
                fh.write("\n_无命中。_\n\n")
                continue
            best10 = uterms.sort_values("best_rank").head(10)
            fh.write("- best_rank 最好的 10 个：\n")
            for _, r in best10.iterrows():
                cat = "【品类】" if r["is_category"] else ""
                tr = f", trend={r['trend_ratio']}" if pd.notna(r["trend_ratio"]) else ""
                fh.write(f"    - {cat}{r['term']} (best_rank={r['best_rank']}, "
                         f"present={r['months_present']}m{tr}) [{r['matched_keyword']}]\n")
            # 在榜月份分布（识别季节双峰）
            from collections import Counter
            mc = Counter()
            for ml in uterms["months_on_list"]:
                for m in ml.split(";"):
                    if m:
                        mc[m] += 1
            dist = "; ".join(f"{m}:{mc.get(m,0)}" for m in sorted(mc))
            fh.write(f"- 在榜月份分布：{dist}\n\n")
    log(f"已写出 {path}")


# =============================================================================
# 最终汇总 REPORT.md
# =============================================================================

def _hypothesis_all_keywords():
    """HYPOTHESIS_DICT 全部关键词的 token 集合（用于假设空白区判定）。"""
    toks = set()
    for kws in HYPOTHESIS_DICT.values():
        for kw in kws:
            base = kw[:-1] if kw.endswith("*") else kw
            toks.update(tokenize(base.lower()))
    return toks


def build_final_report(wide, ctx, quality, p2, p3, gift_agg, comm_agg, p4c, p4d, p5):
    log("=== 生成 REPORT.md ===")
    months = ctx["months"]
    hyp_tokens = _hypothesis_all_keywords()
    is_cat = wide["is_category"].fillna(False)

    # ---- 机会词候选合并 ----
    cand_terms = set()
    reasons = {}

    def add(term, reason):
        cand_terms.add(term)
        reasons.setdefault(term, set()).add(reason)

    hits = p5["hits"]
    if len(hits):
        for _, r in hits.iterrows():
            if r["is_category"]:
                add(r["term"], "Phase5命中×品类")
            if pd.notna(r["trend_ratio"]) and r["trend_ratio"] < 0.7:
                add(r["term"], "Phase5命中×趋势向好")
    # 品类子集新入榜 / 季节 spike
    ne_cat = wide.loc[p2["new_entrant_mask"] & is_cat.to_numpy(), "term"].tolist()
    for t in ne_cat:
        add(t, "品类新入榜")
    spike_df = p3["spike_df"]
    if len(spike_df):
        for t in spike_df.loc[spike_df["is_category"], "term"].unique():
            add(t, "品类季节spike")
    # 4C 裸场景词中，族含品类成员 或 族内任一成员 trend<0.7
    fam = p4c["families"]
    bare = p4c["bare"]
    if len(bare) and len(fam):
        # 计算每个 bare 词所属种子族是否含品类 / trend<0.7 成员
        seed_has_cat = fam.groupby("seed")["is_category"].any()
        tr_map = wide.set_index("term")["trend_ratio"]
        fam2 = fam.copy()
        fam2["tr"] = fam2["term"].map(tr_map)
        seed_has_goodtrend = fam2.groupby("seed")["tr"].apply(lambda s: (s < 0.7).any())
        for _, r in bare.iterrows():
            for s in str(r["seeds"]).split(";"):
                if not s:
                    continue
                if seed_has_cat.get(s, False) or seed_has_goodtrend.get(s, False):
                    add(r["term"], "裸场景词×优质词族")
                    break

    # 候选表
    if cand_terms:
        cand = wide[wide["term"].isin(cand_terms)][
            ["term", "best_rank", "months_present", "trend_ratio",
             "first_month", "last_month", "is_category"]].copy()
        cand["reasons"] = cand["term"].map(lambda t: "；".join(sorted(reasons[t])))
        cand = cand.sort_values("best_rank")
        write_csv(cand, "candidates.csv")
    else:
        cand = pd.DataFrame()

    # ---- 假设空白区：4A/4B/4C 靠前但不在词典 ----
    def not_in_dict(token_str):
        toks = set(tokenize(str(token_str).lower()))
        return not (toks & hyp_tokens)

    gap_gift = gift_agg[gift_agg["x"].map(not_in_dict)].head(25) if len(gift_agg) else gift_agg
    gap_comm = comm_agg[comm_agg["commemorated_token"].map(not_in_dict)].head(25) if len(comm_agg) else comm_agg
    # 4C 种子现全部来自词典；改为展示「哪些已验证场景捞出最多裸变体」
    if len(fam):
        bare_by_seed = (fam[fam["is_bare_scenario"]].groupby("seed")["term"].nunique()
                        .sort_values(ascending=False))
        top_bare_seed = [(s, int(c)) for s, c in bare_by_seed.head(20).items()]
    else:
        top_bare_seed = []

    # ---- 写报告 ----
    path = os.path.join(OUTPUT_DIR, "REPORT.md")
    total_raw = int(quality["raw_rows"].sum())
    total_clean = int(quality["clean_rows"].sum())
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("# ABA 搜索词隐藏需求挖掘 — 分析报告\n\n")
        fh.write(f"生成时间：{datetime.now():%Y-%m-%d %H:%M:%S}｜数据：美国站 ABA 2025 全年 12 月\n\n")

        # 1 数据概况
        fh.write("## 1. 数据概况\n\n")
        fh.write(f"- 月度原始行合计 **{total_raw:,}** → 清洗后 **{total_clean:,}**"
                 f"（损耗 {total_raw-total_clean:,}，{(total_raw-total_clean)/total_raw*100:.3f}%）\n")
        fh.write(f"- 跨月去重唯一搜索词 **{len(wide):,}**；其中品类词 "
                 f"**{int(is_cat.sum()):,}**（{is_cat.mean()*100:.2f}%）\n")
        fh.write(f"- 全年 12 月覆盖，编码混合（10 UTF-8-BOM + 2 GB18030），详见 `00_data_quality.md`\n\n")

        # 2 各 Phase top 摘要
        fh.write("## 2. 各 Phase 核心发现\n\n")
        fh.write(f"- **Phase 2 生死簿**：新入榜 {p2['counts']['new_entrants'][0]}（品类 {p2['counts']['new_entrants'][1]}）、"
                 f"掉榜 {p2['counts']['dropouts'][0]}（品类 {p2['counts']['dropouts'][1]}）、"
                 f"间歇 {p2['counts']['intermittent'][0]}（品类 {p2['counts']['intermittent'][1]}）\n")
        n_spk = spike_df['term'].nunique() if len(spike_df) else 0
        fh.write(f"- **Phase 3 轨迹**：合格词 {int(p3['eligible_mask'].sum()):,}；"
                 f"seasonal spike 涉及 {n_spk} 词，详见 `03_spike_calendar.md`\n")
        fh.write(f"- **Phase 4A gift**：X {len(gift_agg):,} 个｜**4B 纪念标记**：被纪念 token {len(comm_agg):,} 个｜"
                 f"**4C 词族**：种子 {len(p4c['seeds'])}，裸场景词 **{len(bare):,}**\n")
        nh = hits['term'].nunique() if len(hits) else 0
        fh.write(f"- **Phase 5 假设验证**：命中去重词 {nh:,}，品类命中 "
                 f"{int(hits['is_category'].sum()) if len(hits) else 0}，详见 `05_hypothesis_summary.md`\n\n")

        fh.write("### 4C 裸场景词 top 10（无 gift / 无标记 / 无品类根的隐藏需求）\n\n")
        if len(bare):
            fh.write("| term | best_rank | present | trend | seeds |\n|---|--:|--:|--:|---|\n")
            for _, r in bare.head(10).iterrows():
                tr = f"{r['trend_ratio']:.2f}" if pd.notna(r["trend_ratio"]) else "—"
                fh.write(f"| {r['term']} | {int(r['best_rank'])} | {r['months_present']} | {tr} | {r['seeds']} |\n")
            fh.write("\n")
        else:
            fh.write("_无。_\n\n")

        # 3 机会词候选
        fh.write("## 3. 机会词候选合并清单\n\n")
        fh.write("满足任一条件即入选（Phase5命中×品类 / Phase5命中×趋势<0.7 / 品类新入榜 / "
                 "品类季节spike / 裸场景词×优质词族），去重后按 best_rank 排序。完整表见 `candidates.csv`。\n\n")
        if len(cand):
            fh.write(f"共 **{len(cand)}** 个候选。top 20：\n\n")
            fh.write("| term | best_rank | present | trend | 品类 | 入选理由 |\n|---|--:|--:|--:|:--:|---|\n")
            for _, r in cand.head(20).iterrows():
                tr = f"{r['trend_ratio']:.2f}" if pd.notna(r["trend_ratio"]) else "—"
                cc = "✓" if r["is_category"] else ""
                fh.write(f"| {r['term']} | {int(r['best_rank'])} | {r['months_present']} | "
                         f"{tr} | {cc} | {r['reasons']} |\n")
            fh.write("\n")
        else:
            fh.write("_无候选。_\n\n")

        # 4 假设空白区
        fh.write("## 4. 假设空白区（人工审阅重点）\n\n")
        fh.write("以下 4A/4B 条目词数靠前，但**不落在 HYPOTHESIS_DICT 任何主题**内——"
                 "最可能藏着团队陌生的新场景（4C 已收窄为词典场景的自动扩展，新场景发现主要靠此处人工审阅）。\n\n")
        fh.write("**4A gift 场景 X（词典外，按词数）：** ")
        fh.write(", ".join(f"{r['x']}({r['n_terms']})" for _, r in gap_gift.iterrows()) or "_无_")
        fh.write("\n\n**4B 被纪念对象（词典外，按词数）：** ")
        fh.write(", ".join(f"{r['commemorated_token']}({r['n_terms']})" for _, r in gap_comm.iterrows()) or "_无_")
        fh.write("\n\n**4C 已验证场景的裸变体产出 top（种子 → 裸场景词数，供优先跟进）：** ")
        fh.write(", ".join(f"{s}({c})" for s, c in top_bare_seed) or "_无_")
        fh.write("\n\n")

        # 5 逐主题解读
        fh.write("## 5. 候选主题解读\n\n")
        write_theme_interpretations(fh, hits, months)

        fh.write("\n---\n\n")
        fh.write("_方法论：Phase 2/3/4 为无假设归纳发现，Phase 5 为假设验证；"
                 "词边界匹配无法完全排除语义歧义（如 warrior 可能来自游戏），"
                 "输出清单需人工抽查。拼写变体/同义词未处理，召回不完整。_\n")
    log(f"已写出 {path}")


def write_theme_interpretations(fh, hits, months):
    if not len(hits):
        fh.write("_Phase 5 无命中，略。_\n")
        return
    from collections import Counter
    notes = {
        "戒断康复": "戒酒/戒瘾里程碑送礼，9 月 Recovery Month 常见季节峰；sober anniversary/milestone 是核心。",
        "疾病康复": "癌症幸存者/抗癌纪念，10 月乳腺癌关注月放量；survivor/warrior 需人工排除游戏歧义。",
        "人生重启": "离婚/分手后重启，fresh start / new chapter 送己或送友。",
        "成就节点": "毕业/退休/升职/马拉松完赛，5-6 月毕业季与赛事季为峰。",
        "军警职业": "退伍/部署/护士/消防等职业身份礼，父亲节与退伍纪念日相关。",
        "纪念哀悼": "逝者纪念/骨灰/指纹首饰，无明显季节，常年稳定刚需。",
        "信仰精神": "护佑/守护天使/evil eye 等信仰符号。",
        "关系联结": "异地/情侣对戒/母女父子/闺蜜，节日与婚礼季相关。",
        "心理健康": "焦虑/心理健康/分号（semicolon）符号，鼓励与陪伴表达。",
        "身份仪式": "成人礼/受洗/坚振/sweet 16 等身份节点。",
        "承诺誓约": "承诺戒指/守贞/订婚/重申誓言。",
    }
    for theme in HYPOTHESIS_DICT:
        sub = hits[hits["theme"] == theme].drop_duplicates("term")
        if not len(sub):
            continue
        mc = Counter()
        for ml in sub["months_on_list"]:
            for m in ml.split(";"):
                if m:
                    mc[m] += 1
        peak = ", ".join(f"{m}({c})" for m, c in mc.most_common(3))
        ncat = int(sub["is_category"].sum())
        fh.write(f"### {theme}（命中 {sub['term'].nunique()}，品类 {ncat}）\n\n")
        fh.write(f"- {notes.get(theme,'')}\n")
        fh.write(f"- 在榜高峰月：{peak}\n")
        fh.write(f"- 建议验证：挑 best_rank 靠前且 is_category=True 的组合词做小额广告测试，"
                 f"观察是否可低成本承接该场景需求。\n\n")


# =============================================================================
# 主流程
# =============================================================================

def main():
    ensure_output_dir()
    long_df, quality = phase0_load_and_clean()
    wide = phase1_build_master(long_df)
    ctx = prepare_context(wide)

    p2 = phase2_lifecycle(wide, ctx)
    p3 = phase3_trajectory(wide, ctx)
    gift_agg = phase4a_gift(wide, ctx)
    comm_agg = phase4b_commemoration(wide, ctx)
    p5 = phase5_hypothesis(wide, ctx)
    p4c = phase4c_snowball(wide, ctx, gift_agg, comm_agg)
    p4d = phase4d_category(wide, ctx)

    build_final_report(wide, ctx, quality,
                       p2=p2, p3=p3, gift_agg=gift_agg, comm_agg=comm_agg,
                       p4c=p4c, p4d=p4d, p5=p5)

    list_outputs()
    log("全部 Phase 完成。")


def list_outputs():
    log("=== output/ 目录清单 ===")
    for f in sorted(glob.glob(os.path.join(OUTPUT_DIR, "*"))):
        base = os.path.basename(f)
        if f.endswith(".csv"):
            try:
                n = sum(1 for _ in open(f, encoding="utf-8-sig")) - 1
            except Exception:
                n = "?"
            print(f"    {base:42s} {n} 行")
        else:
            print(f"    {base:42s} ({os.path.getsize(f)//1024} KB)")


if __name__ == "__main__":
    main()
