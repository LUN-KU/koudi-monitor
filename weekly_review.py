"""每週復盤：統計本週警示的事後表現，發 Telegram 週報。

用法：python3 weekly_review.py [--dry] [--days 7]
"""
import datetime
import sys

import alerts
import notify
import quote

BULLISH = ("進場候選", "進場觀察", "轉強")
BEARISH = ("賣訊", "警戒")


def main():
    dry = "--dry" in sys.argv
    days = 7
    if "--days" in sys.argv:
        days = int(sys.argv[sys.argv.index("--days") + 1])
    cutoff = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()

    entries = [e for e in alerts.load() if e["date"] >= cutoff]
    if not entries:
        msg = f"<b>📈 每週復盤</b>\n\n近 {days} 天沒有任何警示紀錄，無法統計。"
        print(msg) if dry else notify.send(msg)
        return

    prices = quote.get_prices(sorted({e["stk"] for e in entries}))
    rows = []
    for e in entries:
        q = prices.get(e["stk"])
        if not q or not e.get("price"):
            continue
        ret = (q["price"] - e["price"]) / e["price"] * 100
        correct = ret > 0 if e["kind"] in BULLISH else ret < 0
        rows.append({**e, "now": q["price"], "ret": ret, "correct": correct})

    lines = [f"<b>📈 每週復盤（近 {days} 天）</b>", ""]
    for group, names in (("看多訊號", BULLISH), ("看空訊號", BEARISH)):
        g = [r for r in rows if r["kind"] in names]
        if not g:
            continue
        hit = sum(1 for r in g if r["correct"])
        avg = sum(r["ret"] for r in g) / len(g)
        lines.append(f"<b>{group}</b>：{len(g)} 筆，方向正確 {hit} 筆"
                     f"（{hit / len(g) * 100:.0f}%），平均後續漲跌 {avg:+.1f}%")

    best = sorted([r for r in rows if r["kind"] in BULLISH], key=lambda r: -r["ret"])[:3]
    worst = sorted([r for r in rows if r["kind"] in BULLISH], key=lambda r: r["ret"])[:3]
    if best:
        lines += ["", "<b>表現最好的看多訊號</b>"]
        lines += [f"• {r['date']} {r['stk']} {r['name']} {r['price']}→{r['now']} ({r['ret']:+.1f}%)" for r in best]
    if worst and len(best) + len(worst) <= len([r for r in rows if r["kind"] in BULLISH]):
        lines += ["", "<b>表現最差的看多訊號</b>"]
        lines += [f"• {r['date']} {r['stk']} {r['name']} {r['price']}→{r['now']} ({r['ret']:+.1f}%)" for r in worst]

    kinds = {}
    for r in rows:
        kinds[r["kind"]] = kinds.get(r["kind"], 0) + 1
    lines += ["", "<b>訊號數量</b>：" + "、".join(f"{k} {v}" for k, v in sorted(kinds.items()))]
    lines += ["", "<i>報酬以復盤當下現價計算，僅供策略校準參考，非投資建議。</i>"]

    msg = "\n".join(lines)
    print(msg) if dry else notify.send(msg)


if __name__ == "__main__":
    main()
