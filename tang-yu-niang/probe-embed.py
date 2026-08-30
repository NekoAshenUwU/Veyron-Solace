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
import argparse, importlib, json, os, sys, urllib.error, urllib.request

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
    ap.add_argument("--list-models", action="store_true",
                    help="列出这个账号能用的模型，并顺带证明 key 和地址本身是通的")
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

    if a.list_models:
        # 为什么要这一步：/v1/embeddings 返回 404 的时候，光看那一个 404 分不清
        # 是「这家没有这个接口」还是「key/地址有问题」。打一个【一定存在】的
        # 接口(/v1/models)：它通了就说明 key 和 base 都对，那 embeddings 的 404
        # 只可能是这条路由本身不存在——换任何模型名都到不了。
        base = S.EMBED_URL.rsplit("/", 1)[0]          # .../v1/embeddings → .../v1
        url = base + "/models"
        print(f"\n先打一个一定存在的接口证明 key 和地址没问题: {url}")
        req = urllib.request.Request(
            url, headers={"Authorization": f"Bearer {key}"}, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                data = json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            print(f"  × HTTP {e.code} —— 连 /models 都不通，那就是 key 或地址的问题，"
                  f"不是接口有没有的问题")
            print(f"    返回: {e.read().decode('utf-8','replace')[:300]}")
            return 1
        except Exception as e:
            print(f"  × {type(e).__name__}: {e}")
            return 1
        names = [m.get("id") for m in data.get("data", [])]
        print(f"  ✓ 通了。这个账号能用的模型（{len(names)} 个）:")
        for n in names:
            print(f"      {n}")
        looks_embed = [n for n in names if n and "embed" in n.lower()]
        print()
        if looks_embed:
            print(f"  里面带 embed 的: {', '.join(looks_embed)} —— 用 --model 试这个")
        else:
            print("  一个带 embed 的都没有。结合 /v1/embeddings 返回 404，")
            print("  结论是这家【不提供】向量接口，换哪个模型名都没用。")
        return 0

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
