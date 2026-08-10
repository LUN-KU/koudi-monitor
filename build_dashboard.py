"""產生扣抵值監測儀表板（自包含 HTML）。

讀 watchlist.json + kdata.json + positions.json，算出：
  1. 觀察清單各標的的進場條件
  2. 持倉各標的的出場條件（停利＋止損）
輸出 dashboard.html。
"""
import html
import json
import os

import strategy

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "dashboard.html")


def fmt(x):
    if x is None:
        return "—"
    x = float(x)
    return str(int(x)) if abs(x - round(x)) < 1e-9 else f"{x:,.2f}".rstrip("0").rstrip(".")


def pct(x):
    return f"{x:+.1f}%"


def load_json(name, default):
    p = os.path.join(HERE, name)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else default


def analyze_all():
    data = strategy.load_kdata()
    out = {}
    for stk, info in data.items():
        r = strategy.analyze(info["rows"])
        if r:
            r["name"] = info["name"]
            out[stk] = r
    return out


# ---------- 資料組裝（今日關鍵價位 ＋ 可選盤中即時價）----------

def build_view(realtime):
    """回傳 {stk: 顯示欄位}。價位用今日關鍵價位（intraday_levels，與盤中提醒一致），
    盤中模式套即時價、否則用最後收盤價。濾網狀態沿用收盤評分（analyze）。"""
    import quote
    data = strategy.load_kdata()
    r_all = analyze_all()
    today = strategy.taiwan_now().date()

    prices = {}
    if realtime:
        try:
            prices = quote.get_prices(list(data))
        except Exception:
            prices = {}

    view = {}
    last_close_date = None
    for stk, info in data.items():
        rows = sorted(info["rows"], key=lambda x: strategy.to_date(x["d"]))
        if not rows:
            continue
        last_dt = strategy.to_date(rows[-1]["d"])
        last_close_date = max(last_close_date, last_dt) if last_close_date else last_dt
        hist = rows[:-1] if last_dt == today else rows
        lv = strategy.intraday_levels(hist)
        if not lv:
            continue
        q = prices.get(stk)
        today_close = rows[-1]["c"] if last_dt == today else None
        # 只採用 >0 的即時價，否則退回收盤價，避免 0 報價算出 -100%
        live_price = q["price"] if (q and q["price"] > 0) else None
        price = live_price if live_price is not None else (today_close if today_close is not None else rows[-1]["c"])
        prev_close = lv["prev_close"]
        ana = r_all.get(stk)
        trigger = max(lv["ded"], lv["prev_high"])
        stop = lv["prev_low"]
        ma5 = (lv["ma5_partial"] + price) / 5
        dev = (price - ma5) / ma5 * 100  # 乖離率
        # 用與盤中通知完全相同的訊號邏輯（含乖離守門、訊號B止跌轉折）
        sigs = strategy.intraday_signals(lv, price)
        entry = next((s for s in sigs if s["kind"] in ("進場觀察", "止跌轉折", "轉強")), None)
        view[stk] = {
            "name": info["name"], "price": price,
            "chg": (price - prev_close) / prev_close * 100 if prev_close else 0,
            "trigger": trigger, "gap": (trigger - price) / price * 100, "dev": dev, "ma5": ma5,
            "stop": stop, "stop_gap": (stop - price) / price * 100, "breached": price <= stop,
            "ded": lv["ded"], "ded_gap": (lv["ded"] - price) / price * 100, "below_ded": price < lv["ded"],
            "killed": ana["killed"] if ana else [], "score": ana["score"] if ana else 0,
            "exits": ana["exits"] if ana else [],
            "entry_kind": entry["kind"] if entry else None,
            "wk_base": lv.get("wk_base"),
            "wk_gap": ((lv["wk_base"] - price) / price * 100) if lv.get("wk_base") else None,
            "live": bool(live_price is not None),
        }
    return view, last_close_date


# ---------- HTML ----------

CSS = """
:root{
  --bg:#f5f6f8; --panel:#ffffff; --ink:#1a1f2b; --muted:#5b6472; --line:#e3e6ec;
  --accent:#12897e; --up:#d33b30; --down:#1a9e5c; --warn:#c9812a; --warnbg:#fbf1de;
  --chip:#eef0f4;
}
@media (prefers-color-scheme:dark){
  :root{
    --bg:#10141c; --panel:#161c27; --ink:#e8ecf3; --muted:#94a0b2; --line:#242c3a;
    --accent:#2bb6a8; --up:#e0483d; --down:#28ac67; --warn:#f2a33c; --warnbg:#2a2113;
    --chip:#1e2634;
  }
}
:root[data-theme="light"]{
  --bg:#f5f6f8; --panel:#ffffff; --ink:#1a1f2b; --muted:#5b6472; --line:#e3e6ec;
  --accent:#12897e; --up:#d33b30; --down:#1a9e5c; --warn:#c9812a; --warnbg:#fbf1de; --chip:#eef0f4;
}
:root[data-theme="dark"]{
  --bg:#10141c; --panel:#161c27; --ink:#e8ecf3; --muted:#94a0b2; --line:#242c3a;
  --accent:#2bb6a8; --up:#e0483d; --down:#28ac67; --warn:#f2a33c; --warnbg:#2a2113; --chip:#1e2634;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang TC","Noto Sans TC",sans-serif;
  line-height:1.5;-webkit-font-smoothing:antialiased}
.wrap{max-width:980px;margin:0 auto;padding:20px 16px 60px}
.num{font-variant-numeric:tabular-nums}
header{display:flex;flex-wrap:wrap;align-items:baseline;gap:8px 14px;
  padding-bottom:16px;border-bottom:1px solid var(--line);margin-bottom:24px}
h1{font-size:20px;letter-spacing:.02em;margin:0;font-weight:650}
.sub{color:var(--muted);font-size:13px}
.chips{display:flex;gap:8px;margin-left:auto;flex-wrap:wrap}
.chip{background:var(--chip);border-radius:999px;padding:3px 11px;font-size:12.5px;color:var(--muted)}
.chip b{color:var(--ink);font-weight:650}
h2{font-size:13px;text-transform:uppercase;letter-spacing:.12em;color:var(--accent);
  margin:32px 0 12px;font-weight:650}
h2:first-of-type{margin-top:8px}
.eyebrow{color:var(--muted);text-transform:none;letter-spacing:0;font-weight:500;font-size:12px;margin-left:6px}
/* 持倉卡 */
.pos{background:var(--panel);border:1px solid var(--line);border-left:4px solid var(--warn);
  border-radius:12px;padding:14px 16px;margin-bottom:14px}
.pos-hd{display:flex;flex-wrap:wrap;align-items:baseline;gap:6px 12px;margin-bottom:10px}
.code{font-weight:650;font-size:16px}
.pos-hd .price{color:var(--muted);font-size:14px}
.pnl{margin-left:auto;font-weight:650;font-size:15px}
.up{color:var(--up)} .down{color:var(--down)}
.cond{display:grid;grid-template-columns:auto 1fr auto;gap:8px 12px;font-size:13.5px;align-items:baseline}
.cond .k{font-weight:600;white-space:nowrap}
.k.stop{color:var(--warn)} .k.profit{color:var(--up)} .k.warn{color:var(--warn)} .k.ok{color:var(--muted)}
.cond .v{color:var(--ink)}
.cond .d{color:var(--muted);text-align:right;white-space:nowrap;font-size:12.5px}
.empty{background:var(--panel);border:1px dashed var(--line);border-radius:12px;
  padding:20px;color:var(--muted);font-size:14px}
.empty code{background:var(--chip);padding:1px 6px;border-radius:5px;font-size:12.5px}
/* 觀察表 */
.tablewrap{overflow-x:auto;border:1px solid var(--line);border-radius:12px;background:var(--panel)}
table{border-collapse:collapse;width:100%;font-size:13.5px;min-width:640px}
th,td{padding:9px 12px;text-align:right;white-space:nowrap}
th{color:var(--muted);font-weight:600;font-size:11.5px;text-transform:uppercase;letter-spacing:.05em;
  border-bottom:1px solid var(--line);position:sticky;top:0;background:var(--panel)}
td{border-bottom:1px solid var(--line)}
tr:last-child td{border-bottom:none}
.name{text-align:left}
.pill{display:inline-block;padding:2px 9px;border-radius:999px;font-size:11.5px;font-weight:600}
.pill.go{background:color-mix(in srgb,var(--accent) 18%,transparent);color:var(--accent)}
.pill.watch{background:var(--chip);color:var(--muted)}
.pill.bad{background:color-mix(in srgb,var(--warn) 16%,transparent);color:var(--warn)}
.foot{margin-top:28px;color:var(--muted);font-size:12px;line-height:1.7}
.foot b{color:var(--ink)}
"""


def render(realtime=False):
    view, last_close_date = build_view(realtime)
    positions = load_json("positions.json", {})
    watchlist = load_json("watchlist.json", {})
    tw = strategy.taiwan_now()

    if last_close_date:
        d = last_close_date
        wk = "一二三四五六日"[d.weekday()]
        last_d = f"{d.year}/{d.month:02d}/{d.day:02d}（週{wk}）"
    else:
        last_d = "—"

    if realtime:
        mode = f'盤中即時 · 更新 {tw.strftime("%m/%d %H:%M")}'
        price_note = "現價為盤中即時價"
        refresh = '<meta http-equiv="refresh" content="180">'
    else:
        mode = f'收盤 · 資料日 {last_d}'
        price_note = "現價為收盤價快照"
        refresh = ""

    # 持倉區
    pos_rows = []
    for stk, pos in positions.items():
        v = view.get(stk)
        if not v:
            continue
        stop = pos.get("stop") or v["stop"]
        price = v["price"]
        triggered = v["below_ded"] or bool(v["exits"])
        if v["below_ded"]:
            exit_txt = "跌破扣抵值，觸發賣訊"
        elif v["exits"]:
            exit_txt = "；".join(v["exits"])
        else:
            exit_txt = "守扣抵值續抱"
        pos_rows.append({
            "stk": stk, "name": v["name"], "price": price, "chg": v["chg"],
            "stop": stop, "stop_gap": (stop - price) / price * 100, "breached": price <= stop,
            "ded": v["ded"], "ded_gap": v["ded_gap"],
            "cost": pos.get("cost"), "triggered": triggered, "exit_txt": exit_txt,
        })
    pos_rows.sort(key=lambda p: (not p["triggered"], not p["breached"], p["stop_gap"]))

    trs_pos = []
    for p in pos_rows:
        pnl_cell = "—"
        if p["cost"]:
            pl = (p["price"] - p["cost"]) / p["cost"] * 100
            pnl_cell = f'<span class="num {"up" if pl >= 0 else "down"}">{pct(pl)}</span>'
        stop_cls = "warn" if p["breached"] else ""
        move = (f'<span class="pill bad">⚠️ 了結</span>' if p["triggered"]
                else '<span class="pill watch">續抱</span>')
        trs_pos.append(
            f'<tr><td class="name">{p["stk"]} {html.escape(p["name"])}</td>'
            f'<td class="num">{fmt(p["price"])}</td>'
            f'<td class="num {"up" if p["chg"] >= 0 else "down"}">{pct(p["chg"])}</td>'
            f'<td>{pnl_cell}</td>'
            f'<td class="num {stop_cls}">{fmt(p["stop"])}</td>'
            f'<td class="num">{pct(p["stop_gap"])}</td>'
            f'<td class="num">{fmt(p["ded"])}</td>'
            f'<td class="num">{pct(p["ded_gap"])}</td>'
            f'<td class="name" style="white-space:normal">{move} '
            f'<span style="color:var(--muted);font-size:12px">{html.escape(p["exit_txt"])}</span></td>'
            f'</tr>')
    if not trs_pos:
        pos_section = ('<div class="empty">目前沒有持倉。買進後告訴我，或執行：<br>'
                       '<code>python3 manage_positions.py --add 代號 成本=價格 股數=張數 停損=價格 目標=價格</code>'
                       '<br>加入後這裡就會顯示每檔的止損與賣訊條件。</div>')
    else:
        pos_section = (
            '<div class="tablewrap"><table><thead><tr>'
            '<th class="name">標的</th><th>現價</th><th>漲跌</th><th>損益</th>'
            '<th>止損</th><th>距止損</th><th>賣訊(扣抵值)</th><th>距賣訊</th>'
            '<th class="name">移動出場</th></tr></thead><tbody>'
            + "".join(trs_pos) + '</tbody></table></div>')

    # 觀察清單表（狀態＝與盤中通知相同的訊號邏輯：含乖離守門、訊號B）
    def watch_rank(v):
        # 有進場訊號的最前，其次候選，被濾網刪的最後
        return (0 if v["entry_kind"] else (2 if v["killed"] else 1), -v["score"])
    watch = sorted(((s, v) for s, v in view.items() if s in watchlist and s not in positions),
                   key=lambda sv: watch_rank(sv[1]))
    trs = []
    for stk, v in watch:
        # 進場參考價分兩種模式：貼近 MA5→突破價(站上扣抵值/昨高)；已漲多站上 MA5→回測 MA5 參考價
        pullback = v["dev"] > 3   # 站上 MA5 逾 3% 視為漲多，改看回測
        ref = v["ma5"] if pullback else v["trigger"]
        ref_gap = (ref - v["price"]) / v["price"] * 100
        if v["entry_kind"]:
            status, cls = v["entry_kind"], "go"          # 進場觀察／止跌轉折／轉強
            detail = "訊號成立，可留意進場"
        elif v["killed"]:
            status, cls = "不符濾網", "bad"
            detail = "；".join(v["killed"])
        elif v["dev"] > 7:
            status, cls = "乖離過大·不追", "bad"
            detail = f"乖離 {v['dev']:+.1f}%，漲多，等回測 MA5≈{fmt(v['ma5'])} 不破再進"
        elif pullback:
            status, cls = "漲多·等回測", "watch"
            detail = f"已站上 MA5 {v['dev']:+.1f}%，等回測 MA5≈{fmt(v['ma5'])} 不破再進，不追突破"
        else:
            status, cls = "觀察中", "watch"
            detail = (f"貼近 MA5，站上 {fmt(ref)}（突破）才進，還差 {ref_gap:+.1f}%" if ref_gap > 0
                      else "已站上突破價，等訊號全滿足")
        # 週基準價提示（只提示、不改狀態）：現價離週MA5基準價太遠代表週線壓力未過、追高風險大
        if not v["killed"] and v.get("wk_gap") is not None:
            wg = v["wk_gap"]
            if wg > 5:
                detail += f"｜距週基準價 {fmt(v['wk_base'])} 還 +{wg:.1f}%（週MA5未翻揚，追高留意）"
            elif wg > 0:
                detail += f"｜距週基準價 +{wg:.1f}%"
            else:
                detail += "｜已站上週基準價（週MA5翻揚）"
        chg_cls = "up" if v["chg"] >= 0 else "down"
        dev_cls = "up" if v["dev"] >= 0 else "down"
        risk = (v["price"] - v["stop"]) / v["price"] * 100
        ref_cell = "—" if v["killed"] else fmt(ref)          # 被濾網刪的不給進場參考
        gap_cell = "—" if v["killed"] else pct(ref_gap)
        trs.append(
            f'<tr><td class="name">{stk} {html.escape(v["name"])}</td>'
            f'<td class="num">{fmt(v["price"])}</td>'
            f'<td class="num {chg_cls}">{pct(v["chg"])}</td>'
            f'<td><span class="pill {cls}">{status}</span></td>'
            f'<td class="num">{ref_cell}</td>'
            f'<td class="num">{gap_cell}</td>'
            f'<td class="num {dev_cls}">{pct(v["dev"])}</td>'
            f'<td class="num">{fmt(v["stop"])}</td>'
            f'<td class="num">{risk:.1f}%</td>'
            f'<td class="name" style="white-space:normal;color:var(--muted);font-size:12px">{html.escape(detail)}</td>'
            f'</tr>')
    table = (
        '<div class="tablewrap"><table><thead><tr>'
        '<th class="name">標的</th><th>現價</th><th>漲跌</th><th>狀態</th>'
        '<th>進場參考</th><th>距參考</th><th>乖離</th><th>停損</th><th>風險</th>'
        '<th class="name">說明</th></tr></thead><tbody>'
        + "".join(trs) + '</tbody></table></div>')

    return f"""<title>扣抵值監測儀表板</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
{refresh}
<style>{CSS}</style>
<div class="wrap">
<header>
  <h1>扣抵值監測儀表板</h1>
  <span class="sub">{mode}</span>
  <div class="chips">
    <span class="chip">持倉 <b>{len(pos_rows)}</b></span>
    <span class="chip">觀察 <b>{len(watch)}</b></span>
  </div>
</header>

<h2>我的持倉 · 出場條件<span class="eyebrow">止損＋賣訊，跌破即出</span></h2>
{pos_section}

<h2>觀察清單 · 進場條件<span class="eyebrow">狀態＝與盤中通知同一套訊號（含乖離守門）</span></h2>
{table}

<div class="foot">
<b>怎麼看：</b>進場參考＝貼近 MA5 的股票顯示「突破價」（站上才進）；已漲多站上 MA5 的顯示「回測 MA5 參考價」（等拉回不破再進，不追突破）。乖離＝現價離 MA5 多遠；風險＝現價到停損的距離。<br>
狀態（與盤中 Telegram 通知同一套邏輯）：<b>進場觀察／止跌轉折／轉強</b>＝訊號成立可留意｜<b>觀察中</b>＝貼近 MA5、等突破｜<b>漲多·等回測</b>＝站上 MA5 一段、等回測 MA5｜<b>乖離過大·不追</b>＝離 MA5 逾 7%｜<b>不符濾網</b>＝暫不列入。<br>
持倉「止損」跌破就出、「賣訊(扣抵值)」跌破＝第一賣訊、「移動出場」守扣抵值續抱、跌破轉弱才了結。
關鍵價位（止損／扣抵值／觸發）為當日固定值、由前一日收盤算出，與盤中提醒一致；{price_note}。<br>
本頁為技術面判斷輔助，非投資建議，不代表買賣建議。
</div>
</div>"""


def main(realtime=None):
    import sys
    if realtime is None:
        realtime = "--realtime" in sys.argv
    open(OUT, "w", encoding="utf-8").write(render(realtime))
    print("已產生", OUT, "（盤中即時）" if realtime else "（收盤）")


if __name__ == "__main__":
    main()
