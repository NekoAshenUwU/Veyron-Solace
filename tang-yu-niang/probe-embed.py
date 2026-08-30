#!/usr/bin/env python3
"""
问一次：这个供应商到底能不能算向量。

写这个是因为 DeepSeek 官方文档我这边打不开，搜到的说法互相矛盾——
deepseek-ai 仓库里有两个 issue 是【在申请】加 embedding 接口（说明当时没有），
另一边有第三方博客说有。与其猜，不如拿你的 key 真发一次请求。

DeepSeek 的 API 是 OpenAI 兼容的，所以【真有 embeddings 的话不用改代码】，
改 TANG_EMBED_URL / TANG_EMBED_MODEL / TANG_EMBED_KEY_ENV 三个环境变量就行。

跑法（key 从 /root/mcp-oauth.env 自己读，不用 export）：
    PYTHONPATH=/root python3 probe-embed.py --deepseek
    PYTHONPATH=/root python3 probe-embed.py --deepseek --model deepseek-embedding
    PYTHONPATH=/root python3 probe-embed.py --gemini
    PYTHONPATH=/root python3 probe-embed.py            # 按当前环境变量试

全程不打印 key，只打印它的长度。
"""
import argparse, importlib, json, os, sys, urllib.error

PRESETS = {
    "deepseek": dict(TANG_EMBED_API="openai",
                     TANG_EMBED_URL="https://api.deepseek.com/v1/embeddings",
                     TANG_EMBED_MODEL="deepseek-embedding",
                     TANG_EMBED_KEY_ENV="DEEPSEEK_API_KEY"),
    "gemini":   dict(TANG_EMBED_API="gemini",
                     TANG_EMBED_KEY_ENV="GEMINI_API_KEY"),
    "openai":   dict(TANG_EMBED_API="openai",
                     TANG_EMBED_KEY_ENV="OPENAI_API_KEY"),
}


def main() -> int:
    ap = argparse.ArgumentParser()
    for name in PRESETS:
        ap.add_argument(f"--{name}", action="store_true")
    ap.add_argument("--model", help="覆盖模型名（供应商换了名字时用）")
    ap.add_argument("--url", help="覆盖完整 URL")
    a = ap.parse_args()

    for name, env in PRESETS.items():
        if getattr(a, name):
            os.environ.update(env)
            break
    if a.model:
        os.environ["TANG_EMBED_MODEL"] = a.model
    if a.url:
        os.environ["TANG_EMBED_URL"] = a.url

    sys.modules.pop("tang_yu_niang.semantic", None)
    S = importlib.import_module("tang_yu_niang.semantic")

    key = S._api_key()
    print(f"  接口形状 : {S.API}")
    print(f"  地址     : {S.EMBED_URL}")
    print(f"  模型     : {S.EMBED_MODEL}")
    print(f"  key 变量 : {S.KEY_ENV}  →  " +
          (f"读到了，长度 {len(key)}" if key else "【没读到】"))
    if not key:
        print(f"\n× {S.KEY_ENV} 在环境变量和 {S.ENV_FILE} 里都没有（或者值是空的）。")
        return 1

    print("\n发两条短文本试试…")
    try:
        vecs = S.embed(["今天有点累", "想你了"])
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:400]
        print(f"× HTTP {e.code} {e.reason}")
        print(f"  返回: {body}")
        print()
        if e.code == 404:
            print("  404 = 这个地址没有这个接口。多半就是这家不提供 embeddings，")
            print("  或者模型名不对 —— 用 --model 换个名字再试一次。")
        elif e.code in (401, 403):
            print("  401/403 = key 不对或没这个权限，不是接口不存在。")
        elif e.code == 400:
            print("  400 = 接口在、但参数不对，最常见是模型名。用 --model 换一个。")
        return 1
    except Exception as e:
        print(f"× {type(e).__name__}: {e}")
        return 1

    print(f"  ✓ 成了。返回 {len(vecs)} 条向量，每条 {len(vecs[0])} 维。")
    print("\n这套配置能用，写进 /root/mcp-oauth.env：")
    for k in ("TANG_EMBED_API", "TANG_EMBED_URL", "TANG_EMBED_MODEL", "TANG_EMBED_KEY_ENV"):
        v = os.environ.get(k)
        if v:
            print(f"  {k}={v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
