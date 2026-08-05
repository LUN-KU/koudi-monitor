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
    low = [r["l"] for r in rows]
    prev = rows[-1]
    return {
        "base": c[-5],            # 今天的基準價（今天面對的壓力）
        "ded": c[-4],             # 今天的扣抵值（明天的基準價）
        "ma5_partial": sum(c[-4:]),  # 加上今天現價再除 5 = 今天的 MA5
        "prev_close": prev["c"],
        "prev_high": prev["h"],
        "prev_low": prev["l"],
        "prev_d": prev["d"],
        "ded_falling": sum(c[-3:]) / 3 < c[-5],   # 扣抵值遞減趨勢（未來要扣的比基準低）
        "recent_low": min(low[-3:]),              # 近三日最低，判斷「不再創新低」
    }


ENTRY_MAX_DEV = 0.07  # 進場乖離上限：離今日 MA5 逾 7% 視為追高，不報進場


def intraday_signals(lv, price, max_entry_dev=ENTRY_MAX_DEV):
    """比對現價與關鍵價位，回傳觸發的訊號清單（dict）。
    賣訊帶 stop_level（＝停損點，用扣抵值），供 stop_gate 做時間閘控。
    進場訊號加乖離守門：離 MA5 太遠（追高區）不報，符合策略「站上扣抵值要在 MA5 附近轉折、不追噴出紅棒」。"""
    ma5 = (lv["ma5_partial"] + price) / 5
    dev = (price - ma5) / ma5  # 乖離率
    near_ma5 = dev <= max_entry_dev
    gap_flip = (lv["ded"] - price) / price * 100  # 還要漲幾% 才站上扣抵值（<=0 已站上）
    sigs = []
    if near_ma5 and price > lv["base"] and price >= lv["ded"] and price > lv["prev_high"]:
        sigs.append({"kind": "進場觀察",
                     "detail": f"站上扣抵值 {lv['ded']}、過昨高 {lv['prev_high']}（乖離 {dev * 100:+.1f}%）"})
    elif (near_ma5 and lv["ded_falling"] and price >= lv["recent_low"]
          and -2 <= gap_flip <= 2 and price > lv["prev_high"]):
        # 訊號B 止跌轉折：扣抵值下降＋不創新低＋貼近扣抵值(漲1~2%即可翻揚MA5)＋過昨高
        sigs.append({"kind": "止跌轉折",
                     "detail": f"貼扣抵值 {lv['ded']}(差{gap_flip:+.1f}%)、不創新低、過昨高（乖離 {dev * 100:+.1f}%）"})
    elif near_ma5 and price >= lv["ded"] and lv["prev_close"] < lv["ded"]:
        sigs.append({"kind": "轉強", "detail": f"由下站回扣抵值 {lv['ded']}（乖離 {dev * 100:+.1f}%）"})
    if price < lv["ded"] and lv["prev_close"] >= lv["ded"]:
        sigs.append({"kind": "賣訊", "detail": f"跌破扣抵值（停損點）{lv['ded']}",
                     "stop_level": lv["ded"]})
    if price < lv["prev_low"]:
        sigs.append({"kind": "警戒", "detail": f"跌破昨日低點 {lv['prev_low']}"})
    if price < ma5 and lv["prev_close"] >= ma5:
        sigs.append({"kind": "警戒", "detail": f"跌破 MA5 {ma5:.2f}"})
    return sigs


def taiwan_now():
    """台灣時間（不論主機時區，雲端跑在 UTC 也正確）。"""
    return datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=8)


def stop_gate(price, stop_level, tw=None, deep_pct=7.0, confirm=(13, 15)):
    """停損訊號時間閘控。回傳 (是否現在發送, 附註文字)。

    規則：13:15 前先按住不發，除非急殺跌破停損點逾 7%（立即出場）；
    到 13:15 仍沒站回停損點才發出止損出場通知。
    """
    tw = tw or taiwan_now()
    if price <= stop_level * (1 - deep_pct / 100):
        return True, f"急殺跌破停損點逾{deep_pct:.0f}%，立即出場"
    if (tw.hour, tw.minute) >= confirm:
        return True, f"{confirm[0]:02d}:{confirm[1]:02d} 仍未站回停損點，確認止損出場"
    return False, None
