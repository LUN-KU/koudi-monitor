"""盤中掃描：抓觀察清單即時現價，比對扣抵值／基準價等關鍵價位，觸發即發 Telegram。

簡化版：不做五分 K 量能突破確認（需券商資料），訊號僅作初篩，進場前請自行看盤確認。
用法：python3 intraday_scan.py [--dry]
"""
import datetime
import sys

import alerts
import notify
import quote
import strategy

PRIORITY = {"賣訊": 0, "進場觀察": 1, "轉強": 2, "警戒": 3}


def main():
    dry = "--dry" in sys.argv
    data = strategy.load_kdata()
    today = datetime.date.today()

    levels = {}
    for stk, info in data.items():
        rows = sorted(info["rows"], key=lambda r: strategy.to_date(r["d"]))
        if rows and strategy.to_date(rows[-1]["d"]) == today:
            rows = rows[:-1]
        lv = strategy.intraday_levels(rows)
        if lv:
            levels[stk] = (info["name"], lv)

    prices = quote.get_prices(list(levels))
    hits = []
    for stk, (name, lv) in levels.items():
        q = prices.get(stk)
        if not q:
            continue
        for kind, detail in strategy.intraday_signals(lv, q["price"]):
            if alerts.sent_today(kind, stk):
                continue
            hits.append({"kind": kind, "stk": stk, "name": name,
                         "price": q["price"], "detail": detail,
                         "chg": (q["price"] - lv["prev_close"]) / lv["prev_close"] * 100})

    if not hits:
        print("盤中掃描：無新訊號", datetime.datetime.now().strftime("%H:%M"))
        return

    hits.sort(key=lambda h: (PRIORITY.get(h["kind"], 9), -abs(h["chg"])))
    tracked = alerts.tracked()
    lines = [f"<b>⚡ 盤中訊號 {datetime.datetime.now().strftime('%m/%d %H:%M')}</b>", ""]
    for h in hits:
        icon = {"賣訊": "🔴", "警戒": "🟡", "進場觀察": "🟢", "轉強": "🔵"}.get(h["kind"], "•")
        mark = "（持有中）" if h["stk"] in tracked else ""
        lines.append(f"{icon} <b>{h['kind']}</b> {h['stk']} {h['name']} "
                     f"{h['price']} ({h['chg']:+.1f}%){mark}\n   {h['detail']}")
    lines.append("")
    lines.append("<i>簡化版初篩訊號，進場前請自行確認量能與五分 K。非投資建議。</i>")
    msg = "\n".join(lines)

    if dry:
        print(msg)
        return
    notify.send(msg)
    for h in hits:
        alerts.log(h["kind"], h["stk"], h["name"], h["price"], h["detail"], "intraday")
    print("已發送盤中訊號", len(hits), "筆")


if __name__ == "__main__":
    main()
