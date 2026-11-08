# -*- coding: utf-8 -*-
"""候选模型实测：可用性 + 延迟"""
import json
import ssl
import time
import urllib.request
import urllib.error

BASE = "https://tokenhub.tencentmaas.com/v1"
KEY = None
with open("/opt/daily-news/config.json", "r", encoding="utf-8") as f:
    KEY = json.load(f)["llm"]["api_key"]

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

CANDIDATES = [
    "glm-5.3-flash",
    "mimo-v2.6-flash",
    "deepseek/deepseek-flash",
    "kimi-k3.1-pro-highspeed",
    "hy3",
    "hy4",
    "glm-5.3",
    "deepseek-v4-flash-0731",
]

for model in CANDIDATES:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "用一句话介绍今天是什么日子，20字以内。"}],
        "max_tokens": 60,
    }
    req = urllib.request.Request(
        BASE + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": "Bearer " + KEY, "Content-Type": "application/json"},
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=90, context=ctx) as r:
            body = json.loads(r.read().decode("utf-8"))
            cost = time.time() - t0
            reply = body.get("choices", [{}])[0].get("message", {}).get("content", "")[:20]
            print("OK   %-28s %5.1fs  %s" % (model, cost, reply.replace("\n", " ")))
    except urllib.error.HTTPError as e:
        print("HTTP %-28s code=%s %s" % (model, e.code, e.read().decode("utf-8", "replace")[:120]))
    except Exception as e:
        print("FAIL %-28s %s" % (model, str(e)[:70]))
