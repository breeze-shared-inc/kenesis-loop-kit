#!/usr/bin/env python3
"""ループメトリクス集計

tickets/.metrics.jsonl（record_metrics.py が追記するイベントログ）を読み、
サイクルタイム・フェーズ別滞留時間・差し戻し・blocked発生を集計して表示する。
/metrics コマンドから呼ばれる。

使い方:
    python3 .claude/metrics/aggregate.py [--path tickets/.metrics.jsonl] [FILTER]

FILTER を渡すと ticket / project に部分一致するイベントのみ対象にする。
依存なし（Python3標準ライブラリのみ）。
"""
import datetime
import json
import os
import sys

PHASE_ORDER = {
    "todo": 0,
    "investigation_done": 1,
    "design_done": 2,
    "implementation_done": 3,
    "test_passed": 4,
    "done": 5,
}


def human(seconds):
    seconds = int(seconds)
    if seconds < 0:
        seconds = 0
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, _ = divmod(seconds, 60)
    parts = []
    if days:
        parts.append("%dd" % days)
    if hours:
        parts.append("%dh" % hours)
    if minutes or not parts:
        parts.append("%dm" % minutes)
    return " ".join(parts)


def parse_ts(value):
    try:
        return datetime.datetime.fromisoformat(value)
    except Exception:
        return None


def load_events(path, filter_str):
    events = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except Exception:
                continue
            if filter_str:
                hay = "%s %s" % (ev.get("ticket", ""), ev.get("project", ""))
                if filter_str.lower() not in hay.lower():
                    continue
            events.append(ev)
    return events


def main():
    args = sys.argv[1:]
    path = os.path.join("tickets", ".metrics.jsonl")
    filter_str = None
    i = 0
    while i < len(args):
        if args[i] == "--path" and i + 1 < len(args):
            path = args[i + 1]
            i += 2
        else:
            filter_str = args[i]
            i += 1

    if not os.path.exists(path):
        print("メトリクスログがまだありません: %s" % path)
        print("ループを少なくとも1回進めるとイベントが記録されます。")
        return

    events = load_events(path, filter_str)
    if not events:
        print("対象イベントがありません（フィルタ: %s）" % (filter_str or "なし"))
        return

    # チケットごとに時系列で整理
    by_ticket = {}
    for ev in events:
        by_ticket.setdefault(ev.get("ticket"), []).append(ev)
    for evs in by_ticket.values():
        evs.sort(key=lambda e: e.get("ts", ""))

    now = datetime.datetime.now()
    cycle_times = []          # (ticket, seconds)
    dwell_totals = {}         # status -> [seconds,...]
    rollbacks = {}            # "from→to" -> count（実装ループ内の差し戻し）
    rollback_by_ticket = {}   # ticket -> count
    improvements = {}         # "from→to" -> count（done起点の改善ループ）
    improvement_by_ticket = {}  # ticket -> count
    blocked_events = []       # (ticket, ts)
    in_progress = []          # (ticket, status, age_seconds)

    for ticket, evs in by_ticket.items():
        first_ts = parse_ts(evs[0].get("ts"))
        done_ts = None

        for idx, ev in enumerate(evs):
            frm = ev.get("from")
            to = ev.get("to")
            ts = parse_ts(ev.get("ts"))

            # フェーズ滞留: to に入った時刻 ～ 次イベント時刻
            if ts is not None and to is not None:
                if idx + 1 < len(evs):
                    nxt = parse_ts(evs[idx + 1].get("ts"))
                    if nxt is not None:
                        dwell_totals.setdefault(to, []).append(
                            (nxt - ts).total_seconds()
                        )

            # 後退遷移の分類: done起点は改善ループ（人間判断による再開）、
            # それ以外（test_passed起点）は実装ループ内の差し戻し
            if frm in PHASE_ORDER and to in PHASE_ORDER:
                if PHASE_ORDER[to] < PHASE_ORDER[frm]:
                    key = "%s→%s" % (frm, to)
                    if frm == "done":
                        improvements[key] = improvements.get(key, 0) + 1
                        improvement_by_ticket[ticket] = (
                            improvement_by_ticket.get(ticket, 0) + 1)
                    else:
                        rollbacks[key] = rollbacks.get(key, 0) + 1
                        rollback_by_ticket[ticket] = (
                            rollback_by_ticket.get(ticket, 0) + 1)

            if to == "blocked":
                blocked_events.append((ticket, ev.get("ts")))
            if to == "done":
                done_ts = ts

        if first_ts is not None and done_ts is not None:
            cycle_times.append((ticket, (done_ts - first_ts).total_seconds()))

        # 現在進行中（最終ステータスが done/cancelled 以外）
        last_to = evs[-1].get("to")
        last_ts = parse_ts(evs[-1].get("ts"))
        if last_to not in ("done", "cancelled") and last_ts is not None:
            in_progress.append((ticket, last_to, (now - last_ts).total_seconds()))

    # ---- 出力 ----
    print("=== Kenesis Loop Kit メトリクス ===")
    print("イベント数: %d / チケット数: %d%s"
          % (len(events), len(by_ticket),
             ("  フィルタ: %s" % filter_str) if filter_str else ""))
    print()

    print("— サイクルタイム（created → done） —")
    if cycle_times:
        for ticket, sec in sorted(cycle_times, key=lambda x: -x[1]):
            print("  %-16s %s" % (ticket, human(sec)))
        avg = sum(s for _, s in cycle_times) / len(cycle_times)
        print("  平均: %s（完了 %d 件）" % (human(avg), len(cycle_times)))
    else:
        print("  完了チケットなし")
    print()

    print("— フェーズ別 平均滞留時間 —")
    any_dwell = False
    for status in sorted(dwell_totals, key=lambda s: PHASE_ORDER.get(s, 99)):
        vals = dwell_totals[status]
        if vals:
            any_dwell = True
            avg = sum(vals) / len(vals)
            print("  %-20s 平均 %-8s (n=%d)" % (status, human(avg), len(vals)))
    if not any_dwell:
        print("  データ不足")
    print()

    print("— 差し戻し（rollback） —")
    total_rb = sum(rollbacks.values())
    if total_rb:
        print("  総数: %d" % total_rb)
        for key, cnt in sorted(rollbacks.items(), key=lambda x: -x[1]):
            print("    %-28s %d" % (key, cnt))
        worst = sorted(rollback_by_ticket.items(), key=lambda x: -x[1])
        print("  チケット別: " + ", ".join("%s×%d" % (t, c) for t, c in worst))
    else:
        print("  なし")
    print()

    print("— 改善ループ（done起点の再開） —")
    total_imp = sum(improvements.values())
    if total_imp:
        print("  総数: %d" % total_imp)
        for key, cnt in sorted(improvements.items(), key=lambda x: -x[1]):
            print("    %-28s %d" % (key, cnt))
        worst = sorted(improvement_by_ticket.items(), key=lambda x: -x[1])
        print("  チケット別: " + ", ".join("%s×%d" % (t, c) for t, c in worst))
    else:
        print("  なし")
    print()

    print("— blocked 発生 —")
    if blocked_events:
        print("  総数: %d" % len(blocked_events))
        for ticket, ts in blocked_events:
            print("    %-16s %s" % (ticket, ts))
    else:
        print("  なし")
    print()

    print("— 現在進行中 —")
    if in_progress:
        for ticket, status, age in sorted(in_progress, key=lambda x: -x[2]):
            print("  %-16s %-20s 経過 %s" % (ticket, status, human(age)))
    else:
        print("  なし")


if __name__ == "__main__":
    main()
