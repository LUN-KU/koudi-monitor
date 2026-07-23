"""扣抵值策略大腦：濾網、評分、進出場訊號、盤中關鍵價位。

策略依據：../000_Agent/knowledge/扣抵值選股策略.md
"""
import collections
import datetime
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
KDATA = os.path.join(HERE, "kdata.json")


def load_kdata():
    data = json.load(open(KDATA))
    return {k: v for k, v in data.items() if not k.startswith("_")}


def to_date(dstr):
    """民國日期 '115/07/18' → date"""
    y, m, d = dstr.split("/")
    return datetime.date(int(y) + 1911, int(m), int(d))


def _weekly_bars(rows):
    wk = collections.OrderedDict()
    for r in rows:
        w = to_date(r["d"]).isocalendar()[1]
        wk.setdefault(w, {"o": r["o"], "h": r["h"], "l": r["l"], "c": r["c"], "v": 0})
        b = wk[w]
        b["h"] = max(b["h"], r["h"])
        b["l"] = min(b["l"], r["l"])
        b["c"] = r["c"]
        b["v"] += r["v"] or 0
    return list(wk.values())


def analyze(rows):
    """跑完整濾網＋評分。rows 需已含當日收盤（收盤掃描用）。"""
    rows = sorted(rows, key=lambda r: to_date(r["d"]))
    if len(rows) < 12:
        return None
    c = [r["c"] for r in rows]; h = [r["h"] for r in rows]
    l = [r["l"] for r in rows]; o = [r["o"] for r in rows]; v = [r["v"] for r in rows]
    last = rows[-1]
    last_month = to_date(last["d"]).month

    prev_m = [r for r in rows if to_date(r["d"]).month != last_month]
    cur_m = [r for r in rows if to_date(r["d"]).month == last_month]
    if not prev_m or not cur_m:
        return None
    pm_high = max(r["h"] for r in prev_m)
    pm_low = min(r["l"] for r in prev_m)
    dist_pmh = (pm_high - last["c"]) / last["c"] * 100
    broke_pm_low = min(r["l"] for r in cur_m) < pm_low

    wl = _weekly_bars(rows)
    if len(wl) < 2:
        return None
    thisw, lastw = wl[-1], wl[-2]
    broke_lastw_low = thisw["c"] < lastw["l"]
    wcloses = [b["c"] for b in wl]
    ma5w = sum(wcloses[-5:]) / 5 if len(wcloses) >= 5 else None
    below_ma5w = bool(ma5w and thisw["c"] < ma5w)
    w_ded_rising = len(wcloses) >= 5 and (sum(wcloses[-4:-1]) / 3 > wcloses[-5])
    w_ded_falling = len(wcloses) >= 5 and (sum(wcloses[-4:-1]) / 3 < wcloses[-5])

    ma5 = sum(c[-5:]) / 5
    base = c[-6]        # 今天的基準價
    ded = c[-5]         # 今天的扣抵值＝明天的基準價
    fut = c[-4:-1]      # 未來幾天的扣抵值
    d_ded_rising = sum(fut) / 3 > base
    d_ded_falling = sum(fut) / 3 < base
    above_ma5 = last["c"] >= ma5
    gap_flip = (ded - last["c"]) / last["c"] * 100

    chg = last["c"] - c[-2]
    volup = v[-1] > v[-2]
    red = last["c"] > last["o"]
    body = abs(last["c"] - last["o"])
    upsh = last["h"] - max(last["c"], last["o"])
    long_upsh = upsh > body and upsh / last["c"] > 0.015
    pv_bad_black = chg < 0 and volup and (c[-2] - last["c"]) / c[-2] > 0.03
    lows_rising = l[-1] >= l[-2] >= l[-3]
    open_low_after_red = (c[-2] > o[-2]) and (last["o"] < c[-2])
    breakout = last["c"] > h[-2] and volup and red
    no_newhigh_10 = last["c"] < max(h[-11:-1])

    sigA = (base > max(c[-5:-1])) and (last["c"] >= ded * 0.995) and (chg > -last["c"] * 0.01)
    sigB = d_ded_falling and (l[-1] >= min(l[-4:-1])) and (gap_flip <= 2)
    sigC = d_ded_rising and breakout

    killed = []
    if last["c"] < pm_high and dist_pmh > 8:
        killed.append(f"距上月高點{dist_pmh:.1f}%>8%")
    if broke_pm_low:
        killed.append("跌破上月低點")
    if broke_lastw_low:
        killed.append("跌破上週低點")
    if w_ded_rising and below_ma5w:
        killed.append("週扣抵升+破五週均線")
    if pv_bad_black:
        killed.append("價跌量增長黑")
    if not above_ma5:
        killed.append("MA5之下未站回")

    score = 0; notes = []
    if sigA: score += 3; notes.append("A逆勢守壓")
    if sigB: score += 3; notes.append("B止跌轉折")
    if sigC: score += 2; notes.append("C帶量突破")
    if d_ded_falling and w_ded_falling: score += 2; notes.append("日週扣抵同降")
    if last["c"] >= pm_high or dist_pmh <= 3: score += 2; notes.append("近上月高點")
    if chg >= 0: score += 2; notes.append("逆勢抗跌")
    if (chg > 0 and volup) or (chg < 0 and not volup): score += 1; notes.append("量價正常")
    if lows_rising: score += 1; notes.append("低點墊高")
    if ma5w and len(wcloses) >= 6 and sum(wcloses[-5:]) / 5 > sum(wcloses[-6:-1]) / 5:
        score += 1; notes.append("週MA5上揚")
    if long_upsh: score -= 2; notes.append("-長上引線")
    if d_ded_rising and no_newhigh_10: score -= 2; notes.append("-扣抵升未創高")
    if open_low_after_red: score -= 1; notes.append("-紅K後開低")

    # 出場提醒（策略檔「五、出場與風控」）
    exits = []
    if last["c"] < ded:
        exits.append("跌破扣抵值（第一賣訊）")
    if w_ded_rising and below_ma5w:
        exits.append("週扣抵升＋破五週均線（出場）")
    if d_ded_rising and long_upsh:
        exits.append("扣抵升＋長上引線（警戒）")
    if d_ded_rising and pv_bad_black:
        exits.append("扣抵升＋價跌量增長黑（警戒）")

    return {
        "close": last["c"], "chg_pct": round(chg / c[-2] * 100, 2),
        "ma5": round(ma5, 2), "base": base, "ded": ded,
        "gap_flip_pct": round(gap_flip, 2), "dist_pmh_pct": round(dist_pmh, 1),
        "prev_month_high": pm_high, "killed": killed, "score": score, "notes": notes,
        "stop": l[-1], "prev_high": last["h"],
        "d_ded": "降" if d_ded_falling else ("升" if d_ded_rising else "平"),
        "w_ded": "降" if w_ded_falling else ("升" if w_ded_rising else "平"),
        "exits": exits, "last_d": last["d"],
    }


def intraday_levels(rows):
    """盤中用：rows 為「不含今天」的歷史日 K，算出今天要盯的關鍵價位。"""
    rows = sorted(rows, key=lambda r: to_date(r["d"]))
    if len(rows) < 8:
        return None
    c = [r["c"] for r in rows]
    prev = rows[-1]
    return {
        "base": c[-5],            # 今天的基準價（今天面對的壓力）
        "ded": c[-4],             # 今天的扣抵值（明天的基準價）
        "ma5_partial": sum(c[-4:]),  # 加上今天現價再除 5 = 今天的 MA5
        "prev_close": prev["c"],
        "prev_high": prev["h"],
        "prev_low": prev["l"],
        "prev_d": prev["d"],
    }


def intraday_signals(lv, price):
    """比對現價與關鍵價位，回傳觸發的訊號清單。"""
    ma5 = (lv["ma5_partial"] + price) / 5
    sigs = []
    if price > lv["base"] and price >= lv["ded"] and price > lv["prev_high"]:
        sigs.append(("進場觀察", f"站上扣抵值 {lv['ded']} 並過昨高 {lv['prev_high']}"))
    elif price >= lv["ded"] and lv["prev_close"] < lv["ded"]:
        sigs.append(("轉強", f"由下站回扣抵值 {lv['ded']}"))
    if price < lv["ded"] and lv["prev_close"] >= lv["ded"]:
        sigs.append(("賣訊", f"跌破扣抵值 {lv['ded']}（策略第一賣訊）"))
    if price < lv["prev_low"]:
        sigs.append(("警戒", f"跌破昨日低點 {lv['prev_low']}"))
    if price < ma5 and lv["prev_close"] >= ma5:
        sigs.append(("警戒", f"跌破 MA5 {ma5:.2f}"))
    return sigs
