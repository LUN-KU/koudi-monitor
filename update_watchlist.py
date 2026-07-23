"""維護觀察清單 watchlist.json。

用法：
  python3 update_watchlist.py --add 2330=台積電 6414=樺漢
  python3 update_watchlist.py --remove 1301 1303
  python3 update_watchlist.py --set 2330=台積電 ...      （整份取代）
  python3 update_watchlist.py --prune-kills             （移除今天被濾網刪掉的標的）
  python3 update_watchlist.py --list
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WL = os.path.join(HERE, "watchlist.json")


def load():
    return json.load(open(WL, encoding="utf-8"))


def save(d):
    json.dump(d, open(WL, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def parse_pairs(args):
    out = {}
    for a in args:
        if "=" not in a:
            print(f"格式要 代號=名稱，跳過：{a}")
            continue
        k, v = a.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def main():
    argv = sys.argv[1:]
    if not argv or "--list" in argv:
        wl = load()
        print(f"觀察清單 {len(wl)} 檔：")
        for k, v in wl.items():
            print(f"  {k} {v}")
        return

    cmd = argv[0]
    rest = argv[1:]
    wl = load()

    if cmd == "--add":
        new = parse_pairs(rest)
        added = [k for k in new if k not in wl]
        wl.update(new)
        save(wl)
        print(f"已加入 {len(added)} 檔：{added}；清單共 {len(wl)} 檔")
    elif cmd == "--remove":
        gone = [k for k in rest if wl.pop(k, None) is not None]
        save(wl)
        print(f"已移除 {len(gone)} 檔：{gone}；清單共 {len(wl)} 檔")
    elif cmd == "--set":
        wl = parse_pairs(rest)
        save(wl)
        print(f"清單已整份取代，共 {len(wl)} 檔")
    elif cmd == "--prune-kills":
        import strategy
        data = strategy.load_kdata()
        drop = []
        for stk, info in data.items():
            r = strategy.analyze(info["rows"])
            if r and r["killed"]:
                drop.append((stk, info["name"], r["killed"]))
        for stk, name, why in drop:
            wl.pop(stk, None)
            print(f"移除 {stk} {name}：{'；'.join(why)}")
        save(wl)
        print(f"共移除 {len(drop)} 檔，清單剩 {len(wl)} 檔")
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
