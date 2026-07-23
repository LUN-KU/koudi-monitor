"""抓 TWSE 即時報價（免登入）。上市 tse_、上櫃 otc_，自動 fallback。"""
import json
import time
import urllib.request

API = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch={}&json=1&delay=0"
HDR = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer": "https://mis.twse.com.tw/stock/index.jsp",
}
CHUNK = 40


def _f(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def _fetch(chs):
    url = API.format("|".join(chs))
    req = urllib.request.Request(url, headers=HDR)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode("utf-8")).get("msgArray") or []


def get_prices(stks):
    """回傳 {代號: {'price':現價, 'vol':成交量, 'name':名稱}}；抓不到的代號不會出現。"""
    out = {}
    pending = list(stks)
    for prefix in ("tse", "otc"):
        if not pending:
            break
        misses = []
        for i in range(0, len(pending), CHUNK):
            batch = pending[i:i + CHUNK]
            try:
                arr = _fetch([f"{prefix}_{s}.tw" for s in batch])
            except Exception:
                misses += batch
                continue
            got = set()
            for m in arr:
                # z=成交價，成交前為 '-'，退而用 y=昨收 或 最佳買價
                price = _f(m.get("z"))
                if price is None:
                    price = _f((m.get("b") or "-").split("_")[0])
                if price is None:
                    price = _f(m.get("y"))
                if price is None:
                    continue
                out[m["c"]] = {"price": price, "vol": _f(m.get("v")) or 0, "name": m.get("n", "")}
                got.add(m["c"])
            misses += [s for s in batch if s not in got]
            time.sleep(1)
        pending = misses
    return out
