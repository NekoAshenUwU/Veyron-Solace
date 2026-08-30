"""
语义召回：把文本变成向量，按意思找相似的记忆。

为什么要它：memory_reflex 是【子串匹配】，说「累」能命中，说「心情不好」
一个都命中不了——词表里没这四个字。语义召回补的就是这个洞。

为什么走 API 不在本机跑：2026-08-29 看了 VPS，swap 已经用掉三分之一，
内存本来就紧。再塞一个几百 MB 常驻的模型进去，最可能的结果是 mcp 或
tang-web 被 OOM 杀掉。向量【存】起来才 800KB，吃内存的是跑模型不是存向量。

只用标准库（urllib），不新增依赖——mcp 那个 venv 不该为这个动。

配置全走环境变量，换供应商不用改代码：
    TANG_EMBED_URL      默认 https://api.openai.com/v1/embeddings
    TANG_EMBED_MODEL    默认 text-embedding-3-small
    TANG_EMBED_KEY_ENV  默认 OPENAI_API_KEY（指向哪个环境变量存着 key）
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import urllib.error
import urllib.request
from array import array

EMBED_URL = os.environ.get("TANG_EMBED_URL", "https://api.openai.com/v1/embeddings")
EMBED_MODEL = os.environ.get("TANG_EMBED_MODEL", "text-embedding-3-small")
KEY_ENV = os.environ.get("TANG_EMBED_KEY_ENV", "OPENAI_API_KEY")
TIMEOUT = float(os.environ.get("TANG_EMBED_TIMEOUT", "20"))

# 相似度低于这个就当没找到。
#
# 这条是「宁可空手」在语义这边的落点：向量搜索【永远】能返回最相似的几条，
# 哪怕全都不相关——排序不会告诉你「其实都不像」。没有下限的话，随便说句
# 什么都会捞回三条风马牛不相及的记忆灌进予予的上下文。
MIN_SCORE = float(os.environ.get("TANG_EMBED_MIN_SCORE", "0.35"))

# key 兜底去这个文件里找。
#
# 为什么要这一层：mcp 是 systemd 起的，EnvironmentFile 指着这个文件，所以
# 服务跑起来能看见 key；但你在终端里手跑 embed-memories.py 时 shell 里没有,
# 就会「装好了却一条都算不出来」。要么每次手动 export，要么让代码自己去读——
# 反正它已经知道该读哪个文件了。
ENV_FILE = os.environ.get("TANG_ENV_FILE", "/root/mcp-oauth.env")


def _api_key() -> str:
    """先看环境变量，没有再去 env 文件里翻。翻不到返回空字符串。"""
    key = os.environ.get(KEY_ENV, "").strip()
    if key:
        return key
    try:
        with open(ENV_FILE, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                name, _, value = line.partition("=")
                if name.strip() != KEY_ENV:
                    continue
                # systemd 的 EnvironmentFile 允许值带引号，去掉
                value = value.strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                    value = value[1:-1]
                return value.strip()
    except OSError:
        pass
    return ""


def source_text(title: str | None, content: str | None) -> str:
    return f"{(title or '').strip()}\n{(content or '').strip()}".strip()


def source_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _normalize(vec: list[float]) -> list[float]:
    """存之前先归一化，检索时点积就是余弦，省掉每次算模长。"""
    norm = math.sqrt(sum(x * x for x in vec))
    if norm == 0:
        return vec
    return [x / norm for x in vec]


def pack(vec: list[float]) -> bytes:
    return array("f", _normalize(vec)).tobytes()


def unpack(blob: bytes) -> array:
    a = array("f")
    a.frombytes(blob)
    return a


def dot(a, b) -> float:
    return sum(x * y for x, y in zip(a, b))


def embed(texts: list[str]) -> list[list[float]]:
    """
    一批文本 → 一批向量。失败就抛，由调用方决定要不要吞。

    测试时直接替换这个函数（semantic.embed = 假的），不用联网。
    """
    if not texts:
        return []
    key = _api_key()
    if not key:
        raise RuntimeError(
            f"{KEY_ENV} 既不在环境变量里，也不在 {ENV_FILE} 里，拿不到 API key")

    body = json.dumps({"model": EMBED_MODEL, "input": texts}).encode("utf-8")
    req = urllib.request.Request(
        EMBED_URL,
        data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        payload = json.loads(resp.read().decode("utf-8"))

    # 有的供应商不保证按输入顺序返回，按 index 排一遍
    items = sorted(payload.get("data", []), key=lambda d: d.get("index", 0))
    out = [d["embedding"] for d in items]
    if len(out) != len(texts):
        raise RuntimeError(f"返回了 {len(out)} 个向量，输入是 {len(texts)} 条")
    return out


def search(conn, query: str, limit: int = 2, seen: set | None = None,
           min_score: float | None = None) -> list[dict]:
    """
    按意思找记忆。返回的每条带一个 _score，方便调阈值时看。

    任何异常都吞掉返回 []——这条路是 memory_reflex 的兜底，
    它挂了不该让整次调用挂掉，更不该往上下文里塞错误信息。
    """
    if not query or not query.strip():
        return []
    floor = MIN_SCORE if min_score is None else min_score
    seen = seen or set()

    try:
        qvec = _normalize(embed([query])[0])
    except Exception:
        return []

    try:
        rows = conn.execute(
            "SELECT m.*, v.vec FROM memory_vectors v "
            "JOIN memories m ON m.id = v.memory_id "
            "WHERE v.model = ?", (EMBED_MODEL,),
        ).fetchall()
    except Exception:
        return []

    scored = []
    for r in rows:
        if r["id"] in seen:
            continue
        try:
            score = dot(qvec, unpack(r["vec"]))
        except Exception:
            continue
        if score >= floor:
            d = {k: r[k] for k in r.keys() if k != "vec"}
            d["_score"] = round(score, 4)
            scored.append(d)

    scored.sort(key=lambda d: (-d["_score"], str(d.get("id"))))
    return scored[:limit]
