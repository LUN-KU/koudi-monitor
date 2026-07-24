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
    tw = strategy.taiwan_now()

    # 交易時段守門：非台股盤中（週一~五 09:00–13:35）一律不掃描、不發通知，
    # 避免 GitHub 排程誤點到收盤後才觸發、拿收盤價亂算亂發。
    if not dry and (tw.weekday() >= 5
                    or not (datetime.time(9, 0) <= tw.time() <= datetime.time(13, 35))):
        print("非交易時段，略過盤中掃描", tw.strftime("%m/%d %H:%M"))
        return

    data = strategy.load_kdata()
    today = tw.date()

    levels = {}
    stale = []
    for stk, info in data.items():
        rows = sorted(info["rows"], key=lambda r: strategy.to_date(r["d"]))
        if rows and strategy.to_date(rows[-1]["d"]) == today:
            rows = rows[:-1]
        # 資料新鮮度：最新 K 線離今天超過 6 天視為殘缺/過期，跳過不亂算
        if not rows or (today - strategy.to_date(rows[-1]["d"])).days > 6:
            stale.append(stk)
            continue
        lv = strategy.intraday_levels(rows)
        if lv:
            levels[stk] = (info["name"], lv)
    if stale:
        print("資料過期跳過:", stale)

    prices = quote.get_prices(list(levels))
    hits = []
    for stk, (name, lv) in levels.items():
        q = prices.get(stk)
        if not q:
            continue
        for sig in strategy.intraday_signals(lv, q["price"]):
            kind, detail = sig["kind"], sig["detail"]
            if "stop_level" in sig:
                fire, note = strategy.stop_gate(q["price"], sig["stop_level"], tw)
                if not fire:
                    continue
                detail = f"{detail}｜{note}"
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
    lines = [f"<b>⚡ 盤中訊號 {tw.strftime('%m/%d %H:%M')}</b>", ""]
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
