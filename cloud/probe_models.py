# -*- coding: utf-8 -*-
"""探测 TokenHub 可用模型名与错误详情"""
import json
import ssl
import urllib.request
import urllib.error

BASE = "https://tokenhub.tencentmaas.com/v1"
KEY = None
with open("/opt/daily-news/config.json", "r", encoding="utf-8") as f:
    KEY = json.load(f)["llm"]["api_key"]

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def call(model, timeout=90):
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "回复两个字：好的"}],
        "max_tokens": 20,
    }
    req = urllib.request.Request(
        BASE + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": "Bearer " + KEY, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            body = json.loads(r.read().decode("utf-8"))
            content = body.get("choices", [{}])[0].get("message", {}).get("content", "")
            usage = body.get("usage", {})
            print("OK   %-24s reply=%-10s tokens=%s" % (model, content[:10], usage.get("total_tokens")))
    except urllib.error.HTTPError as e:
        print("HTTP %-24s code=%s body=%s" % (model, e.code, e.read().decode("utf-8", "replace")[:220]))
    except Exception as e:
        print("FAIL %-24s %s" % (model, str(e)[:80]))


try:
    req = urllib.request.Request(BASE + "/models", headers={"Authorization": "Bearer " + KEY})
    with urllib.request.urlopen(req, timeout=30, context=ctx) as r:
        data = json.loads(r.read().decode("utf-8"))
        ids = [m.get("id") for m in data.get("data", [])]
        print("可用模型列表（%d 个）：" % len(ids))
        for i in ids:
            print("  -", i)
except Exception as e:
    print("models 接口不可用：", str(e)[:100])
    for m in ["hunyuan-lite", "hunyuan-turbos-latest", "hunyuan-t1-latest", "hy4", "deepseek-v3"]:
        call(m)
else:
    for m in ids[:12]:
        call(m)
