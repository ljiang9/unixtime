#!/usr/bin/env python3
"""unixtime - Unix 时间戳换算小工具。

纯标准库，纯本地。

用法：
    unixtime 1728000000              # 时间戳 -> 可读日期（本地时区 + UTC，带星期）
    unixtime 1728000000000           # 毫秒时间戳自动识别
    unixtime now                      # 当前时间戳（秒 + 毫秒）
    unixtime "2026-10-05 12:00"      # 日期字符串 -> 时间戳
    unixtime --diff 1728000000 1728086400   # 两时间戳之间的人性化时长
    unixtime 1728000000 --tz Asia/Shanghai --json
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

VERSION = "0.1.0"

WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

# 毫秒/秒判别阈值：>= 1e11 视为毫秒（秒级 1e11 对应公元 5138 年，现实中不会出现）
MS_THRESHOLD = 10 ** 11

DATE_FORMATS = [
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
    "%Y/%m/%d %H:%M:%S",
    "%Y/%m/%d %H:%M",
    "%Y/%m/%d",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M",
    "%Y%m%d%H%M%S",
    "%Y%m%d",
]


def eprint(msg):
    print(msg, file=sys.stderr)


def resolve_tz(name):
    if not name:
        # 本地时区
        return datetime.now().astimezone().tzinfo, None
    try:
        return ZoneInfo(name), name
    except ZoneInfoNotFoundError:
        eprint(f"error: 未知的时区：{name}")
        sys.exit(1)


def parse_timestamp(text):
    """解析时间戳输入，返回（秒, 是否毫秒）。"""
    try:
        n = int(text)
    except ValueError:
        return None
    if abs(n) >= MS_THRESHOLD:
        return n / 1000.0, True
    return float(n), False


def parse_datetime(text, tzinfo):
    """解析日期字符串为带时区的 datetime。"""
    for fmt in DATE_FORMATS:
        try:
            dt = datetime.strptime(text, fmt)
            return dt.replace(tzinfo=tzinfo)
        except ValueError:
            continue
    # 试试 ISO 8601（带时区偏移）
    try:
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=tzinfo)
        return dt
    except ValueError:
        return None


def fmt_dt(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S") + " " + WEEKDAYS[dt.weekday()]


def human_duration(seconds):
    """秒数 -> 人性化时长，如 1 天 2 小时 3 分钟 4 秒。"""
    neg = seconds < 0
    s = int(abs(seconds))
    days, s = divmod(s, 86400)
    hours, s = divmod(s, 3600)
    minutes, s = divmod(s, 60)
    parts = []
    if days:
        parts.append(f"{days} 天")
    if hours:
        parts.append(f"{hours} 小时")
    if minutes:
        parts.append(f"{minutes} 分钟")
    if s or not parts:
        parts.append(f"{s} 秒")
    text = " ".join(parts)
    return ("-" if neg else "") + text


def show_timestamp(ts_seconds, tzinfo, tz_label, as_json):
    dt_local = datetime.fromtimestamp(ts_seconds, tz=tzinfo)
    dt_utc = datetime.fromtimestamp(ts_seconds, tz=timezone.utc)
    ms = int(round(ts_seconds * 1000))
    if as_json:
        print(json.dumps({
            "timestamp_s": int(ts_seconds) if ts_seconds == int(ts_seconds) else ts_seconds,
            "timestamp_ms": ms,
            "local": dt_local.strftime("%Y-%m-%d %H:%M:%S"),
            "local_tz": tz_label or str(tzinfo),
            "local_weekday": WEEKDAYS[dt_local.weekday()],
            "utc": dt_utc.strftime("%Y-%m-%d %H:%M:%S"),
            "utc_weekday": WEEKDAYS[dt_utc.weekday()],
        }, ensure_ascii=False, indent=2))
    else:
        tz_show = tz_label or "本地时区"
        print(f"时间戳：{int(ts_seconds) if ts_seconds == int(ts_seconds) else ts_seconds}（秒）/ {ms}（毫秒）")
        print(f"{tz_show}：{fmt_dt(dt_local)}")
        print(f"UTC：{fmt_dt(dt_utc)}")


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="unixtime",
        description="Unix 时间戳换算：时间戳 <-> 可读日期，纯本地。",
    )
    ap.add_argument("input", nargs="?", help="时间戳（秒/毫秒自动识别）、now、或日期字符串")
    ap.add_argument("--diff", nargs=2, metavar=("TS1", "TS2"),
                    help="计算两个时间戳之间的人性化时长")
    ap.add_argument("--tz", help="显示时区，如 Asia/Shanghai（默认本地时区）")
    ap.add_argument("--json", action="store_true", help="JSON 输出")
    ap.add_argument("--version", action="version", version=f"unixtime {VERSION}")
    args = ap.parse_args(argv)

    # --diff 模式
    if args.diff:
        tzinfo, _ = resolve_tz(args.tz)
        vals = []
        for raw in args.diff:
            parsed = parse_timestamp(raw)
            if parsed is None:
                eprint(f"error: 不是有效的时间戳：{raw}")
                sys.exit(1)
            vals.append(parsed[0])
        delta = vals[1] - vals[0]
        if args.json:
            print(json.dumps({"ts1": vals[0], "ts2": vals[1],
                              "delta_seconds": delta,
                              "human": human_duration(delta)}, ensure_ascii=False))
        else:
            print(f"{vals[0]:.0f} -> {vals[1]:.0f}：相差 {human_duration(delta)}")
        return

    if not args.input:
        ap.error("请提供输入：时间戳、now、日期字符串，或用 --diff")

    raw = args.input.strip()
    tzinfo, tz_label = resolve_tz(args.tz)

    # now
    if raw.lower() == "now":
        ts = datetime.now(tz=timezone.utc).timestamp()
        show_timestamp(ts, tzinfo, tz_label, args.json)
        return

    # 时间戳（秒/毫秒自动识别）
    parsed = parse_timestamp(raw)
    if parsed is not None:
        ts, was_ms = parsed
        if not args.json:
            unit = "毫秒" if was_ms else "秒"
            eprint(f"（识别为{unit}时间戳）")
        show_timestamp(ts, tzinfo, tz_label, args.json)
        return

    # 日期字符串 -> 时间戳
    dt = parse_datetime(raw, tzinfo)
    if dt is None:
        eprint(f"error: 无法解析日期：{raw}")
        eprint("支持格式如：2026-10-05 12:00、2026-10-05、2026/10/05 12:00:00")
        sys.exit(1)
    ts = dt.timestamp()
    show_timestamp(ts, tzinfo, tz_label, args.json)


if __name__ == "__main__":
    main()
