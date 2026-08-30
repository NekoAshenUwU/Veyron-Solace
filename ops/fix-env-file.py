#!/usr/bin/env python3
"""
修 env 文件里被 >> 黏在一起的行。

怎么坏的：`grep ... >> file` 不会先补换行。原文件结尾没换行的话，
追加的内容就长在最后一行屁股上：
    MCP_SECRET=zzzOPENAI_API_KEY=sk-...
【两个】变量一起废：新的读不到，旧的值还被污染了。
systemd 的 EnvironmentFile 也一样读错，不只是我的脚本。

只在指定的变量名前面切，不做通用猜测——值里本来就可能有 = 和字母，
通用规则会把好好的值切碎。默认切 OPENAI_API_KEY，可以用 --name 加别的。

全程不打印任何值，只打印变量名和长度。
    python3 fix-env-file.py                # 只看，不落盘
    python3 fix-env-file.py --apply
"""
import argparse, os, shutil, sys
from datetime import datetime


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="/root/mcp-oauth.env")
    ap.add_argument("--name", action="append", default=None,
                    help="要从行中间切出来的变量名，可给多次")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    names = a.name or ["OPENAI_API_KEY"]

    if not os.path.isfile(a.file):
        print(f"× 找不到 {a.file}", file=sys.stderr)
        return 1

    raw = open(a.file, encoding="utf-8", errors="replace").read()
    lines = raw.splitlines()

    fixed, splits = [], []
    for line in lines:
        cur = line
        # 反复切，一行上可能黏了不止一个
        while True:
            hit = None
            for n in names:
                i = cur.find(n + "=")
                if i > 0:                      # >0：行首那个是正常的，不切
                    if hit is None or i < hit[0]:
                        hit = (i, n)
            if hit is None:
                break
            i, n = hit
            head, tail = cur[:i], cur[i:]
            splits.append((head.split("=", 1)[0], n))
            fixed.append(head)
            cur = tail
        fixed.append(cur)

    def varname(l):
        s = l.strip()
        return s.split("=", 1)[0] if "=" in s and not s.startswith("#") else None

    present = [v for v in (varname(l) for l in fixed) if v]
    dupes = sorted({v for v in present if present.count(v) > 1})

    print(f"文件: {a.file}")
    print(f"  原来 {len(lines)} 行 → 修完 {len([l for l in fixed if l.strip()])} 行（非空）")
    print(f"  结尾有换行: {'有' if raw.endswith(chr(10)) else '【没有】'}")
    if splits:
        print("  黏在一起、要拆开的:")
        for a_, b_ in splits:
            print(f"    {a_}  ←后面黏着→  {b_}")
    else:
        print("  没发现黏行")
    print(f"  修完的变量: {', '.join(present)}")
    if dupes:
        print(f"  ！重复定义: {', '.join(dupes)} —— systemd 用最后一个，自己确认哪个对")

    if not a.apply:
        print("\n（没落盘）确认就加 --apply。会先备份。")
        return 0
    if not splits and raw.endswith("\n"):
        print("\n本来就是好的，没改。")
        return 0

    bak = f"{a.file}.bak-{datetime.now():%Y%m%d-%H%M%S}"
    shutil.copy2(a.file, bak)
    with open(a.file, "w", encoding="utf-8") as fh:
        fh.write("\n".join(fixed).rstrip("\n") + "\n")   # 结尾留换行，下次 >> 不会再黏
    os.chmod(a.file, 0o600)
    print(f"\n  ✓ 修好了，备份 {bak}")
    print("\n！被污染的那个变量的值现在少了尾巴，去备份里对一下是不是本来就该这样。")
    print("改完让 mcp 重新读一遍：  systemctl restart mcp")
    return 0


if __name__ == "__main__":
    sys.exit(main())
