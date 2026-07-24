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


# ---------- 條件文字 ----------

def entry_plan(r):
    trig = max(r["ded"], r["prev_high"])
    gap = (trig - r["close"]) / r["close"] * 100
    risk = (r["close"] - r["stop"]) / r["close"] * 100
    if r["killed"]:
        status, cls = "不符濾網", "bad"
    elif r["score"] >= 3:
        status, cls = "可進場觀察", "go"
    else:
        status, cls = "候選觀察", "watch"
    return {
        "status": status, "cls": cls,
        "trigger": trig, "gap": gap, "stop": r["stop"], "risk": risk,
        "ded": r["ded"], "reason": "；".join(r["killed"]) if r["killed"] else "",
        "notes": "、".join(n for n in r["notes"] if not n.startswith("-")),
    }


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


def render():
    r_all = analyze_all()
    wl = load_json("watchlist.json", {})
    positions = load_json("positions.json", {})
    last_d = max((r["last_d"] for r in r_all.values()),
                 key=lambda d: strategy.to_date(d), default="—")
    if last_d != "—":
        dt = strategy.to_date(last_d)
        last_d = f"{dt.year}/{dt.month:02d}/{dt.day:02d}（週{'一二三四五六日'[dt.weekday()]}）"

    # 持倉區
    pos_rows = []
    for stk, pos in positions.items():
        r = r_all.get(stk)
        if not r:
            continue
        close = r["close"]
        stop = pos.get("stop") or r["stop"]
        ded = r["ded"]
        triggered = bool(r["exits"])
        pos_rows.append({
            "stk": stk, "name": r["name"], "close": close, "chg": r["chg_pct"],
            "stop": stop, "stop_gap": (stop - close) / close * 100,
            "ded": ded, "ded_gap": (ded - close) / close * 100,
            "cost": pos.get("cost"), "target": pos.get("target"),
            "triggered": triggered, "exit_txt": "；".join(r["exits"]) if triggered else "守扣抵值續抱",
            "breached": close <= stop,
        })
    # 最該注意的排前面：已觸發移動出場 > 已破止損 > 距止損近
    pos_rows.sort(key=lambda p: (not p["triggered"], not p["breached"], p["stop_gap"]))

    trs_pos = []
    for p in pos_rows:
        pnl_cell = "—"
        if p["cost"]:
            pl = (p["close"] - p["cost"]) / p["cost"] * 100
            pnl_cell = f'<span class="num {"up" if pl >= 0 else "down"}">{pct(pl)}</span>'
        stop_cls = "warn" if p["breached"] else ""
        move = (f'<span class="pill bad">⚠️ 了結</span>' if p["triggered"]
                else '<span class="pill watch">續抱</span>')
        trs_pos.append(
            f'<tr><td class="name">{p["stk"]} {html.escape(p["name"])}</td>'
            f'<td class="num">{fmt(p["close"])}</td>'
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
                       '<br>加入後這裡就會顯示每檔的止損與停利條件。</div>')
    else:
        pos_section = (
            '<div class="tablewrap"><table><thead><tr>'
            '<th class="name">標的</th><th>現價</th><th>漲跌</th><th>損益</th>'
            '<th>止損</th><th>距止損</th><th>賣訊(扣抵值)</th><th>距賣訊</th>'
            '<th class="name">移動出場</th></tr></thead><tbody>'
            + "".join(trs_pos) + '</tbody></table></div>')

    # 觀察清單表
    rows = sorted(r_all.items(),
                  key=lambda kv: (bool(kv[1]["killed"]), -kv[1]["score"]))
    trs = []
    for stk, r in rows:
        if stk in positions:
            continue
        ep = entry_plan(r)
        chg_cls = "up" if r["chg_pct"] >= 0 else "down"
        detail = ep["reason"] or ep["notes"] or "—"
        trs.append(
            f'<tr><td class="name">{stk} {html.escape(r["name"])}</td>'
            f'<td class="num">{fmt(r["close"])}</td>'
            f'<td class="num {chg_cls}">{pct(r["chg_pct"])}</td>'
            f'<td><span class="pill {ep["cls"]}">{ep["status"]}</span></td>'
            f'<td class="num">{fmt(ep["trigger"])}</td>'
            f'<td class="num">{pct(ep["gap"])}</td>'
            f'<td class="num">{fmt(ep["stop"])}</td>'
            f'<td class="num">{ep["risk"]:.1f}%</td>'
            f'<td class="name" style="white-space:normal;color:var(--muted);font-size:12px">{html.escape(detail)}</td>'
            f'</tr>')
    table = (
        '<div class="tablewrap"><table><thead><tr>'
        '<th class="name">標的</th><th>現價</th><th>漲跌</th><th>狀態</th>'
        '<th>進場觸發</th><th>距觸發</th><th>停損</th><th>風險</th>'
        '<th class="name">說明</th></tr></thead><tbody>'
        + "".join(trs) + '</tbody></table></div>')

    watch_n = len([1 for s in r_all if s not in positions])
    return f"""<title>扣抵值監測儀表板</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>{CSS}</style>
<div class="wrap">
<header>
  <h1>扣抵值監測儀表板</h1>
  <span class="sub">資料日 {last_d}（收盤價）</span>
  <div class="chips">
    <span class="chip">持倉 <b>{len(positions)}</b></span>
    <span class="chip">觀察 <b>{watch_n}</b></span>
  </div>
</header>

<h2>我的持倉 · 出場條件<span class="eyebrow">止損＋停利，跌破即出</span></h2>
{pos_section}

<h2>觀察清單 · 進場條件<span class="eyebrow">觸發＝站上扣抵值且突破昨高</span></h2>
{table}

<div class="foot">
<b>怎麼看：</b>進場觸發＝站上該價位才考慮進場（「距觸發」正值代表還要漲多少）；風險＝現價到停損的距離。
持倉的「止損」跌破就出、「停利目標」到價分批、「移動出場」是守扣抵值續抱、轉弱才了結。<br>
狀態：<b>可進場觀察</b>＝通過濾網且評分高｜<b>候選觀察</b>＝通過濾網｜<b>不符濾網</b>＝暫不列入（說明欄列原因）。<br>
數字為收盤價快照，非即時；本頁為技術面判斷輔助，非投資建議，不代表買賣建議。
</div>
</div>"""


def main():
    open(OUT, "w", encoding="utf-8").write(render())
    print("已產生", OUT)


if __name__ == "__main__":
    main()
