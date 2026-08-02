"""抓觀察清單的日 K 線，存成 kdata.json。

用法: python3 fetch_k.py [YYYYMM_上月] [YYYYMM_本月]
不帶參數則自動抓上月＋本月。
"""
import json, time, urllib.request, sys, os, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "kdata.json")

# 抓取範圍＝觀察清單 ∪ 持倉，確保持倉標的也有 K 線可算出場條件
WATCH = json.load(open(os.path.join(HERE, "watchlist.json")))
_pos_path = os.path.join(HERE, "positions.json")
if os.path.exists(_pos_path):
    for _code, _rec in json.load(open(_pos_path)).items():
        WATCH.setdefault(_code, _rec.get("name") or _code)

MONTHS = sys.argv[1:3] if len(sys.argv) >= 3 else None
if not MONTHS:
    first = datetime.date.today().replace(day=1)
    prev = (first - datetime.timedelta(days=1)).replace(day=1)
    MONTHS = [prev.strftime("%Y%m"), first.strftime("%Y%m")]

HDR = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}


def get(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=HDR)
            with urllib.request.urlopen(req, timeout=15) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(5 * (i + 1))


def f(s):
    if s is None:
        return None
    s = str(s).replace(",", "").replace("X", "").strip()
    try:
        return float(s)
    except Exception:
        return None


def twse(stk, ym):
    d = get(f"https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY?date={ym}01&stockNo={stk}&response=json")
    if d.get("stat") != "OK":
        return None
    rows = []
    for r in d["data"]:
        c = f(r[6])
        if c is None:
            continue
        rows.append({"d": r[0], "o": f(r[3]), "h": f(r[4]), "l": f(r[5]), "c": c, "v": f(r[1])})
    return rows or None


def tpex(stk, ym):
    y = int(ym[:4]); m = ym[4:]
    urls = [
        f"https://www.tpex.org.tw/www/zh-tw/afterTrading/tradingStock?code={stk}&date={y}/{m}/01&response=json",
        f"https://www.tpex.org.tw/web/stock/aftertrading/daily_trading_info/st43_result.php?l=zh-tw&d={y-1911}/{m}&stkno={stk}",
    ]
    for u in urls:
        try:
            d = get(u, tries=1)
        except Exception:
            continue
        data = None
        if isinstance(d, dict):
            if d.get("aaData"):
                data = d["aaData"]
            elif d.get("tables"):
                for t in d["tables"]:
                    if t.get("data"):
                        data = t["data"]; break
        if not data:
            continue
        rows = []
        for r in data:
            c = f(r[6])
            if c is None:
                continue
            rows.append({"d": r[0], "o": f(r[3]), "h": f(r[4]), "l": f(r[5]), "c": c, "v": f(r[1])})
        if rows:
            return rows
    return None


def roc_ym(dstr):
    """民國日期字串 → (西元年, 月)"""
    y, m, _ = dstr.split("/")
    return (int(y) + 1911, int(m))


def fetch_month(stk, ym):
    r = None
    try:
        r = twse(stk, ym)
    except Exception as e:
        print(stk, ym, "twse err", e, file=sys.stderr)
    if r:
        return r, "twse"
    r = tpex(stk, ym)
    return (r, "tpex") if r else (None, None)


def main():
    prev_ym, cur_ym = MONTHS
    prev_key = (int(prev_ym[:4]), int(prev_ym[4:]))

    out = {}
    if os.path.exists(OUT):
        cached = json.load(open(OUT))
        out = {k: v for k, v in cached.items() if k != "_months" and v.get("rows") and k in WATCH}

    for stk, name in WATCH.items():
        existing = out.get(stk, {}).get("rows", [])
        by_date = {r["d"]: r for r in existing}
        src = out.get(stk, {}).get("src")
        have_prev = any(roc_ym(d) == prev_key for d in by_date)

        # 當月一律重抓（每天長新 K 棒）
        cur_rows, s = fetch_month(stk, cur_ym)
        if cur_rows:
            src = s
            for row in cur_rows:
                by_date[row["d"]] = row
        time.sleep(3)

        # 換月盲點修正：月初當月資料還少（或上月未快取）時補抓上月，
        # 才不會漏掉上月最後一個交易日（例：8 月初仍要補抓 7/31）
        if (not have_prev) or (not cur_rows) or (len(cur_rows) < 5):
            prev_rows, s2 = fetch_month(stk, prev_ym)
            if prev_rows:
                src = s2 or src
                for row in prev_rows:
                    by_date[row["d"]] = row
            time.sleep(3)

        rows = sorted(by_date.values(), key=lambda x: tuple(int(p) for p in x["d"].split("/")))
        if rows:
            out[stk] = {"name": name, "src": src, "rows": rows}
            json.dump({**out, "_months": MONTHS}, open(OUT, "w"), ensure_ascii=False)
        print(stk, name, src, len(rows), file=sys.stderr)

    json.dump({**out, "_months": MONTHS}, open(OUT, "w"), ensure_ascii=False)
    print("have:", len(out), "missing:", [k for k in WATCH if k not in out])


if __name__ == "__main__":
    main()
