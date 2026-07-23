"""抓觀察清單的日 K 線，存成 kdata.json。

用法: python3 fetch_k.py [YYYYMM_上月] [YYYYMM_本月]
不帶參數則自動抓上月＋本月。
"""
import json, time, urllib.request, sys, os, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
WATCH = json.load(open(os.path.join(HERE, "watchlist.json")))
OUT = os.path.join(HERE, "kdata.json")

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


def main():
    out = {}
    if os.path.exists(OUT):
        cached = json.load(open(OUT))
        if cached.get("_months") == MONTHS:
            out = {k: v for k, v in cached.items() if k != "_months" and v.get("rows") and k in WATCH}

    for stk, name in WATCH.items():
        if stk in out and len(out[stk]["rows"]) >= 30:
            continue
        rows = []; src = None
        for ym in MONTHS:
            r = None
            try:
                r = twse(stk, ym)
            except Exception as e:
                print(stk, ym, "twse err", e, file=sys.stderr)
            if r:
                src = "twse"
            else:
                r = tpex(stk, ym)
                if r:
                    src = "tpex"
            if r:
                rows += r
            time.sleep(3)
        if rows:
            out[stk] = {"name": name, "src": src, "rows": rows}
            json.dump({**out, "_months": MONTHS}, open(OUT, "w"), ensure_ascii=False)
        print(stk, name, src, len(rows), file=sys.stderr)

    json.dump({**out, "_months": MONTHS}, open(OUT, "w"), ensure_ascii=False)
    print("have:", len(out), "missing:", [k for k in WATCH if k not in out])


if __name__ == "__main__":
    main()
