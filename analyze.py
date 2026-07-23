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
SEED_GENERIC_CUTOFF = 0.005
SEED_MIN_FAMILY_SIZE = 3

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
    """品类词根 → 单个词边界正则；黑名单 → 单个正则。"""
    roots = sorted(set(CATEGORY_ROOTS), key=len, reverse=True)
    root_re = re.compile(r"\b(?:" + "|".join(re.escape(r) for r in roots) + r")\b")
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

def main():
    ensure_output_dir()
    long_df, quality = phase0_load_and_clean()
    wide = phase1_build_master(long_df)
    log("当前已实现 Phase 0-1 全部完成。")


if __name__ == "__main__":
    main()
