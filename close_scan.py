"""收盤掃描：跑完整濾網＋評分，把 Top 標的與出場提醒發到 Telegram。

用法：python3 close_scan.py [--dry]
--dry 只印出訊息，不發送。
"""
import sys
import datetime

import alerts
import notify
import strategy

TOP_N = 10


def build():
    data = strategy.load_kdata()
    results = []
    for stk, info in data.items():
        r = strategy.analyze(info["rows"])
        if r:
            r.update(stk=stk, name=info["name"])
            results.append(r)
    if not results:
        return None, []

    alive = sorted([r for r in results if not r["killed"]],
                   key=lambda r: (-r["score"], r["gap_flip_pct"]))
    dead = [r for r in results if r["killed"]]
    tracked = alerts.tracked()
    exiting = [r for r in results if r["exits"] and r["stk"] in tracked]
    last_d = results[0]["last_d"]

    lines = [f"<b>📊 收盤掃描 {last_d}</b>（觀察清單 {len(results)} 檔）", ""]

    if alive:
        lines.append(f"<b>✅ 通過濾網 {len(alive)} 檔｜Top {min(TOP_N, len(alive))}</b>")
        for i, r in enumerate(alive[:TOP_N], 1):
            lines.append(
                f"{i}. <b>{r['stk']} {r['name']}</b> 收{r['close']} ({r['chg_pct']:+}%) 分{r['score']}\n"
                f"   日扣{r['d_ded']} 週扣{r['w_ded']}｜距上月高 {r['dist_pmh_pct']}%｜翻揚差 {r['gap_flip_pct']}%\n"
                f"   扣抵值 {r['ded']}｜停損 {r['stop']}｜{'、'.join(r['notes']) or '無加分項'}"
            )
    else:
        lines.append("<b>今日無標的通過濾網</b>（環境不佳，寧可空手）")
    lines.append("")

    if exiting:
        lines.append(f"<b>⚠️ 出場／警戒 {len(exiting)} 檔</b>（近期候選／持有中）")
        for r in exiting:
            lines.append(f"• {r['stk']} {r['name']} 收{r['close']}｜{'；'.join(r['exits'])}")
        lines.append("")

    lines.append(f"<i>被濾掉 {len(dead)} 檔。本訊息為技術面判斷輔助，非投資建議。</i>")
    return "\n".join(lines), alive[:TOP_N]


def main():
    msg, top = build()
    if not msg:
        print("沒有可分析的資料，請先跑 fetch_k.py")
        return
    if "--dry" in sys.argv:
        print(msg)
        return
    for r in top:
        alerts.log("進場候選", r["stk"], r["name"], r["close"],
                   f"分{r['score']} {'、'.join(r['notes'])}", "close")
    notify.send(msg)
    print("已發送收盤掃描，Top", len(top), "檔", datetime.date.today())


if __name__ == "__main__":
    main()
