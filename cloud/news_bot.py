# -*- coding: utf-8 -*-
"""
每日热点速览 · 云端自动出刊脚本（Python 3.6+，仅标准库）

流程：拉取 RSS 新闻源 -> 去重筛选 -> （可选）调用大模型生成摘要 -> 生成公众号 HTML
      -> 保存本地 -> 通过微信官方 API 推送到公众号草稿箱

用法：
    python3 news_bot.py              # 完整流程：生成 + 推送草稿箱
    python3 news_bot.py --dry-run    # 只生成 HTML，不推送
    python3 news_bot.py --force      # 今天已有文件也重新生成
"""
import datetime
import json
import os
import re
import ssl
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "config.json")
OUT_DIR = os.path.join(HERE, "out")
LOG_DIR = os.path.join(HERE, "logs")

BASE = "https://api.weixin.qq.com"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"


def log(msg):
    line = "[%s] %s" % (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg)
    print(line)
    if not os.path.isdir(LOG_DIR):
        os.makedirs(LOG_DIR)
    path = os.path.join(LOG_DIR, datetime.datetime.now().strftime("%Y-%m-%d") + ".log")
    with open(path, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def fetch(url, timeout=15, data=None, headers=None):
    h = {"User-Agent": UA}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=data, headers=h)
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        return r.read()


def strip_html(text):
    text = re.sub(r"<[^>]+>", "", text or "")
    text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&quot;", '"')
    text = text.replace("&lt;", "<").replace("&gt;", ">").replace("&#39;", "'")
    return re.sub(r"\s+", " ", text).strip()


FOREIGN_KW = ["美国", "美军", "特朗普", "白宫", "俄罗斯", "俄军", "普京", "乌克兰", "以色列", "伊朗", "日本",
              "韩国", "朝鲜", "印度", "欧盟", "欧洲", "英国", "法国", "德国", "加拿大", "澳大利亚", "巴西",
              "阿根廷", "墨西哥", "菲律宾", "泰国", "越南", "柬埔寨", "缅甸", "新加坡", "马来西亚", "印尼",
              "沙特", "也门", "胡塞", "叙利亚", "土耳其", "埃及", "南非", "联合国", "北约", "加沙",
              "巴勒斯坦", "黎巴嫩", "阿富汗", "巴基斯坦", "塞尔维亚", "波兰", "挪威", "瑞典", "芬兰",
              "荷兰", "西班牙", "意大利", "瑞士", "新西兰", "委内瑞拉", "古巴", "塞内加尔", "阿曼",
              "阿联酋", "卡塔尔", "伊拉克", "约旦", "蒙古", "尼泊尔", "孟加拉", "斯里兰卡"]

SOFT_KW = ["明星", "综艺", "绯闻", "球员", "赛事", "比分", "演唱会", "网红", "直播带货", "美食", "旅游攻略"]


def clean_summary(text, title):
    """清洗 RSS 摘要：去掉电头、记者署名、标题重复"""
    if not text:
        return ""
    t = text
    t = re.sub(r"^(中新网|中新社|新华社|央视新闻|人民网|界面新闻)[^。！？]{0,40}?[电讯]\s*", "", t)
    t = re.sub(r"^【[^】]{0,20}】", "", t)
    t = re.sub(r"[（(][^）)]{0,15}记者[^）)]{0,20}[）)]", "", t)
    t = re.sub(r"^[（(][^）)]{0,20}[）)]", "", t)
    if title and t.startswith(title):
        t = t[len(title):].lstrip("，。： ")
    t = t.replace("#8195;", " ").replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", t).strip()


def is_intl(item):
    text = item["title"] + " " + item["desc"][:60]
    return sum(1 for k in FOREIGN_KW if k in text) >= 1


def classify(domestic, intl):
    """把国内源里的国际新闻挪到国际池，并过滤软新闻"""
    dom, itl = [], list(intl)
    for it in domestic:
        if any(k in it["title"] for k in SOFT_KW):
            continue
        (itl if is_intl(it) else dom).append(it)
    itl = [x for x in itl if not any(k in x["title"] for k in SOFT_KW)]
    return dom, itl


def parse_pub(pub):
    """解析 RSS 时间，失败返回 None"""
    if not pub:
        return None
    pub = pub.strip()
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(pub)
        if dt.tzinfo is not None:
            dt = dt.astimezone().replace(tzinfo=None)
        return dt
    except Exception:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(pub[:19], fmt)
        except Exception:
            continue
    return None


def parse_rss(raw, source_name):
    items = []
    try:
        root = ET.fromstring(raw)
    except Exception:
        return items
    for node in root.iter():
        tag = node.tag.split("}")[-1]
        if tag not in ("item", "entry"):
            continue
        title = desc = link = pub = ""
        for child in node:
            ctag = child.tag.split("}")[-1]
            if ctag == "title":
                title = strip_html(child.text)
            elif ctag in ("description", "summary", "content"):
                desc = strip_html(child.text)
            elif ctag == "link":
                link = (child.text or child.get("href") or "").strip()
            elif ctag in ("pubDate", "published", "updated"):
                pub = (child.text or "").strip()
        if title and len(title) >= 8:
            items.append({
                "title": title,
                "desc": desc[:200],
                "link": link,
                "pub": pub,
                "dt": parse_pub(pub),
                "source": source_name,
            })
    return items


def collect(cfg):
    max_age = int(cfg.get("max_age_hours", 48))
    now = datetime.datetime.now()
    domestic, intl = [], []
    for src in cfg["feeds"]["domestic"]:
        try:
            items = parse_rss(fetch(src["url"]), src["name"])
            fresh = [x for x in items if x["dt"] is None or (now - x["dt"]).total_seconds() < max_age * 3600]
            domestic.extend(fresh)
            log("拉取 %s：%d 条（48h 内 %d 条）" % (src["name"], len(items), len(fresh)))
        except Exception as e:
            log("拉取失败 %s：%s" % (src["name"], e))
    for src in cfg["feeds"]["intl"]:
        try:
            items = parse_rss(fetch(src["url"]), src["name"])
            fresh = [x for x in items if x["dt"] is None or (now - x["dt"]).total_seconds() < max_age * 3600]
            intl.extend(fresh)
            log("拉取 %s：%d 条（48h 内 %d 条）" % (src["name"], len(items), len(fresh)))
        except Exception as e:
            log("拉取失败 %s：%s" % (src["name"], e))
    return dedupe(sort_by_time(domestic)), dedupe(sort_by_time(intl))


def sort_by_time(items):
    return sorted(items, key=lambda x: x["dt"] or datetime.datetime(1970, 1, 1), reverse=True)


def dedupe(items):
    seen, out = set(), []
    for it in items:
        key = re.sub(r"[^\u4e00-\u9fa5A-Za-z0-9]", "", it["title"])[:12]
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out


def call_llm(cfg, domestic, intl):
    """用大模型挑选 20 条并生成摘要，返回 {"domestic":[...], "intl":[...]}"""
    llm = cfg.get("llm", {})
    if not llm.get("enabled") or not llm.get("api_key"):
        return None

    def brief(items, n=22):
        rows = []
        for i, it in enumerate(items[:n]):
            rows.append("%d. %s || %s" % (i + 1, it["title"], it["desc"][:90]))
        return "\n".join(rows)

    prompt = (
        "你是新闻编辑。下面是今天抓取到的国内与国际新闻候选。\n"
        "请从国内候选中挑选 12 条、国际候选中挑选 8 条，共 20 条，要求：\n"
        "1. 优先时政、经济、科技、民生、重大国际事件，避开娱乐八卦与软文广告；\n"
        "2. 每条输出：改写后的标题（不超过 25 字，客观、不用惊叹号）、2 句话摘要（60-90 字，信息密度高）、来源媒体名；\n"
        "3. 输出要求（严格遵守）：只输出一个 JSON 对象，不要任何解释、不要编号清单、不要 markdown 代码块，"
        "第一个字符必须是 { ，最后一个字符必须是 } 。内容必须用简体中文。\n"
        "   格式：{\"domestic\":[{\"title\":\"\",\"summary\":\"\",\"source\":\"\"}],\"intl\":[{\"title\":\"\",\"summary\":\"\",\"source\":\"\"}]}\n\n"
        "【国内候选】\n" + brief(domestic) + "\n\n【国际候选】\n" + brief(intl)
    )
    def try_model(model_name, base_url, api_key):
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": "你是严谨的中文新闻编辑，只输出合法 JSON，不要解释。"},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
            "max_tokens": 8000,
        }
        url = base_url.rstrip("/") + "/chat/completions"
        raw = fetch(url, timeout=180, data=json.dumps(payload).encode("utf-8"),
                    headers={"Authorization": "Bearer " + api_key,
                             "Content-Type": "application/json"})
        msg = json.loads(raw.decode("utf-8"))["choices"][0]["message"]
        text = (msg.get("content") or "") + "\n" + (msg.get("reasoning_content") or "")
        m = re.search(r"\{[\s\S]*\}", text)
        if not m:
            dbg = "/tmp/llm_raw_%s.txt" % model_name.replace("/", "_")
            with open(dbg, "w", encoding="utf-8") as df:
                df.write(text[:6000])
            raise ValueError("输出中找不到 JSON（已存 %s，开头：%s）"
                             % (dbg, text[:150].replace("\n", " ")))
        data = parse_json_loose(m.group(0))
        if len(data.get("domestic", [])) < 3 or len(data.get("intl", [])) < 2:
            raise ValueError("返回条目不足（国内 %d / 国际 %d）"
                             % (len(data.get("domestic", [])), len(data.get("intl", []))))
        return data

    # 模型优先级：默认按 model_chain 顺序尝试，失败自动降级
    default_url = llm.get("base_url", "")
    key = llm.get("api_key", "")
    chain = llm.get("model_chain") or [llm.get("model", "hunyuan-lite")]
    for idx, m in enumerate(chain):
        if isinstance(m, dict):
            name, url, k = m.get("model"), m.get("base_url", default_url), m.get("api_key", key)
        else:
            name, url, k = m, default_url, key
        try:
            data = try_model(name, url, k)
            log("大模型成功：%s（第 %d 顺位）" % (name, idx + 1))
            return data
        except Exception as e:
            log("模型 %s 调用失败：%s" % (name, str(e)[:120]))
            continue
    log("所有模型均失败，回退到无模型模式")
    return None


def fallback(items, n, source_default):
    """无大模型时：清洗摘要，跳过没有可用摘要的条目，按时间顺序取满 n 条"""
    out = []
    for it in items:
        if len(out) >= n:
            break
        desc = clean_summary(it["desc"], it["title"])
        if len(desc) < 25:
            continue
        if len(desc) > 95:
            desc = desc[:93].rstrip("，。、 ") + "…"
        title = it["title"]
        if len(title) > 26:
            title = title[:25] + "…"
        out.append({"title": title, "summary": desc,
                    "source": it.get("source") or source_default})
    return out


def parse_json_loose(raw):
    """容错解析：模型输出被截断时，补齐未闭合的括号与引号后再试"""
    try:
        return json.loads(raw)
    except Exception:
        pass
    text = raw.rstrip()
    # 去掉末尾残缺的对象/数组片段
    for cut in range(len(text), max(len(text) - 400, 0), -1):
        frag = text[:cut]
        fixed = frag + ("]" if frag.count("[") > frag.count("]") else "") + ("}" if frag.count("{") > frag.count("}") else "")
        fixed = fixed.replace(",]", "]").replace(",}", "}")
        try:
            data = json.loads(fixed)
            if isinstance(data, dict):
                return data
        except Exception:
            continue
    raise ValueError("JSON 无法修复（长度 %d）" % len(raw))


def esc(t):
    return (t or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def merge_fill(picked, pool, need, default_source):
    """模型给出的条目不足时，用 RSS 兜底条目补齐到 need 条"""
    out = list(picked)[:need]
    seen = set(re.sub(r"[^\u4e00-\u9fa5A-Za-z0-9]", "", d["title"])[:10] for d in out)
    if len(out) >= need:
        return out
    for item in fallback(pool, need * 3, default_source):
        if len(out) >= need:
            break
        key = re.sub(r"[^\u4e00-\u9fa5A-Za-z0-9]", "", item["title"])[:10]
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def render_builtin(date_str, weekday, issue, guide, domestic, intl):
    GRAD = ("background-color:#1e3a8a;"
            "background-image:-webkit-linear-gradient(135deg,#1e3a8a,#2563eb);"
            "background-image:linear-gradient(135deg,#1e3a8a,#2563eb);")

    def item(idx, d, color):
        return (
            '\n  <table width="100%" cellpadding="0" cellspacing="0" border="0" '
            'style="width:100%;border-collapse:collapse;border:none;margin:18px 0 0;">'
            '<tr>'
            '<td width="26" style="border:none;width:1.7em;vertical-align:top;padding:2px 8px 0 0;">'
            '<span style="display:inline-block;width:1.45em;height:1.45em;line-height:1.45em;'
            'text-align:center;background-color:' + color + ';color:#ffffff;border-radius:50%;'
            '-webkit-border-radius:50%;font-size:0.82em;font-weight:bold;">' + str(idx) + '</span></td>'
            '<td style="border:none;vertical-align:top;padding:0;">'
            '<p style="margin:0;font-size:1.06em;font-weight:bold;color:#1f2937;line-height:1.55;">'
            + esc(d["title"]) + '</p>'
            '<p style="margin:6px 0 0;font-size:0.95em;color:#4b5563;line-height:1.85;">'
            + esc(d["summary"]) + '</p>'
            '<p style="margin:5px 0 0;font-size:0.8em;color:#9aa3b2;line-height:1.6;">来源：'
            + esc(d.get("source", "")) + '</p>'
            '</td></tr></table>'
        )

    def label(text, color):
        return (
            '\n  <table cellpadding="0" cellspacing="0" border="0" '
            'style="border-collapse:collapse;border:none;margin:28px 0 0;"><tr>'
            '<td style="border:none;padding:0;">'
            '<span style="display:inline-block;background-color:' + color + ';color:#ffffff;font-size:0.95em;'
            'font-weight:bold;padding:0.3em 1em;border-radius:1em;-webkit-border-radius:1em;'
            'letter-spacing:2px;">' + text + '</span></td></tr></table>'
            '\n  <table width="100%" cellpadding="0" cellspacing="0" border="0" '
            'style="width:100%;border-collapse:collapse;border:none;margin-top:6px;"><tr>'
            '<td style="border:none;border-top:2px solid #e8eefc;border-left:none;border-right:none;'
            'border-bottom:none;font-size:0;line-height:0;height:0;padding:0;">&nbsp;</td></tr></table>'
        )

    dom_html = "".join(item(i + 1, d, "#2563eb") for i, d in enumerate(domestic))
    intl_html = "".join(item(i + 13, d, "#ea580c") for i, d in enumerate(intl))
    guide_html = "<br>".join("%s %s" % ("①②③④⑤⑥"[i], g) for i, g in enumerate(guide[:6]))

    return (
        '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1"></head>'
        '<body style="margin:0;padding:0;background-color:#f5f7fa;">'
        '<section style="max-width:677px;margin:0 auto;padding:16px 12px;background-color:#ffffff;'
        'font-family:-apple-system,BlinkMacSystemFont,\'PingFang SC\',\'Microsoft YaHei\',sans-serif;'
        'font-size:15px;color:#2b2b2b;line-height:1.8;-webkit-text-size-adjust:100%;">'

        '<section style="' + GRAD + 'padding:26px 16px 22px;text-align:center;'
        'border-radius:14px;-webkit-border-radius:14px;">'
        '<p style="margin:0;color:#adc8ff;font-size:0.8em;letter-spacing:4px;line-height:1.6;">DAILY BRIEFING</p>'
        '<p style="margin:8px 0 0;font-size:1.7em;font-weight:bold;color:#ffffff;letter-spacing:2px;line-height:1.4;">每日热点速览</p>'
        '<p style="margin:10px 0 0;color:#dbe7ff;font-size:0.85em;line-height:1.6;">' +
        date_str + " · " + weekday + " · 第 " + str(issue) + " 期</p></section>"

        '<section style="margin:18px 0 0;background-color:#eef4ff;border-radius:10px;'
        '-webkit-border-radius:10px;padding:14px 16px;">'
        '<p style="margin:0 0 6px;font-size:0.86em;font-weight:bold;color:#2563eb;line-height:1.6;">今日导读</p>'
        '<p style="margin:0;font-size:0.86em;color:#3b4a63;line-height:2;">' + guide_html + '</p></section>'

        + label("国内热点", "#2563eb") + dom_html
        + label("国际热点", "#ea580c") + intl_html +

        '<section style="margin:28px 0 0;background-color:#f4f6f9;border-radius:10px;'
        '-webkit-border-radius:10px;padding:16px;text-align:center;">'
        '<p style="margin:0;font-size:0.86em;color:#6b7280;line-height:1.9;">每天早上 8:00 准时更新，国内外热点一网打尽<br>'
        '觉得有用，欢迎点赞、在看、转发给你的朋友</p></section>'
        '<p style="margin:14px 0 0;font-size:0.75em;color:#c0c5d0;text-align:center;line-height:1.6;">'
        '信息来源为公开网络报道，仅供参考</p>'
        '</section></body></html>'
    )


def load_template(cfg):
    """读取模板文件；缺失时返回 None（走内置版式兜底）"""
    rel = cfg.get("template", "page-template.html")
    path = rel if os.path.isabs(rel) else os.path.join(HERE, rel)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    log("模板文件不存在：%s，改用内置版式" % path)
    return None


def extract_block(tpl, name):
    """提取 <!-- NAME_START --> ... <!-- NAME_END --> 之间的可重复区块"""
    m = re.search(r"<!--\s*%s_START\s*-->([\s\S]*?)<!--\s*%s_END\s*-->" % (name, name), tpl)
    if not m:
        raise ValueError("模板缺少区块标记：%s_START/END" % name)
    return m.group(1)


def fill_item(block, idx, d):
    return (block.replace("{{IDX}}", str(idx))
                 .replace("{{TITLE}}", esc(d.get("title", "")))
                 .replace("{{SUMMARY}}", esc(d.get("summary", "")))
                 .replace("{{SOURCE}}", esc(d.get("source", ""))))


def render(cfg, date_line, guide, domestic, intl):
    """优先用模板文件渲染（单一事实源）；模板缺失时回退内置版式"""
    tpl = load_template(cfg)
    if not tpl:
        parts = date_line.split(" · ")
        date_str = parts[0] if parts else date_line
        weekday = parts[1] if len(parts) > 1 else ""
        issue = 1
        m = re.search(r"第\s*(\d+)\s*期", date_line)
        if m:
            issue = int(m.group(1))
        return render_builtin(date_str, weekday, issue, guide, domestic, intl)

    dom_block = extract_block(tpl, "DOM_ITEM")
    intl_block = extract_block(tpl, "INTL_ITEM")
    dom_html = "".join(fill_item(dom_block, i + 1, d) for i, d in enumerate(domestic))
    # 国际条目序号接着国内往下排，条数变化也不会错号
    intl_html = "".join(fill_item(intl_block, len(domestic) + i + 1, d)
                        for i, d in enumerate(intl))
    guide_html = "<br>".join("%s %s" % ("①②③④⑤⑥"[i], esc(g)) for i, g in enumerate(guide[:6]))

    page = re.sub(r"<!--\s*(DOM|INTL)_ITEM_START\s*-->[\s\S]*?<!--\s*\1_ITEM_END\s*-->", "", tpl)
    page = (page.replace("{{DATE_LINE}}", esc(date_line))
                .replace("{{GUIDE}}", guide_html)
                .replace("{{DOMESTIC}}", dom_html)
                .replace("{{INTL}}", intl_html))
    left = re.findall(r"\{\{[A-Z_]+\}\}", page)
    if left:
        log("警告：模板仍有未替换占位符 %s" % sorted(set(left)))
    log("使用模板渲染：%s" % cfg.get("template", "page-template.html"))
    return page


def wx_token(cfg):
    url = "%s/cgi-bin/token?grant_type=client_credential&appid=%s&secret=%s" % (
        BASE, cfg["appid"], cfg["secret"])
    resp = json.loads(fetch(url).decode("utf-8"))
    if "access_token" not in resp:
        raise RuntimeError("获取 access_token 失败：%s（如为 40164，请把本机公网 IP 加入公众号 IP 白名单）"
                           % json.dumps(resp, ensure_ascii=False))
    return resp["access_token"]


def wx_post(url, payload):
    return json.loads(fetch(url, timeout=60, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                            headers={"Content-Type": "application/json; charset=utf-8"}).decode("utf-8"))


def wx_upload_cover(token, cover_path):
    boundary = "----wbbot%s" % os.urandom(8).hex()
    with open(cover_path, "rb") as f:
        data = f.read()
    body = (("--%s\r\n" % boundary).encode()
            + ('Content-Disposition: form-data; name="media"; filename="%s"\r\n' % os.path.basename(cover_path)).encode()
            + b"Content-Type: image/jpeg\r\n\r\n" + data
            + ("\r\n--%s--\r\n" % boundary).encode())
    url = "%s/cgi-bin/material/add_material?access_token=%s&type=image" % (BASE, token)
    resp = json.loads(fetch(url, timeout=60, data=body,
                            headers={"Content-Type": "multipart/form-data; boundary=%s" % boundary}).decode("utf-8"))
    if "media_id" not in resp:
        raise RuntimeError("上传封面失败：%s" % json.dumps(resp, ensure_ascii=False))
    return resp["media_id"]


def publish(cfg, title, html_path):
    token = wx_token(cfg)
    log("access_token 获取成功")
    cover = os.path.join(HERE, cfg["wechat"].get("cover", "cover.jpg"))
    thumb = wx_upload_cover(token, cover)
    log("封面上传成功")
    with open(html_path, "r", encoding="utf-8") as f:
        content = f.read()
    payload = {"articles": [{
        "title": title,
        "author": cfg["wechat"].get("author", "每日热点速览"),
        "digest": "",
        "content": content,
        "thumb_media_id": thumb,
        "need_open_comment": 1,
        "only_fans_can_comment": 0,
    }]}
    resp = wx_post("%s/cgi-bin/draft/add?access_token=%s" % (BASE, token), payload)
    if resp.get("errcode"):
        raise RuntimeError("新建草稿失败：%s" % json.dumps(resp, ensure_ascii=False))
    log("草稿推送成功 media_id=%s" % resp.get("media_id"))
    return resp.get("media_id")


def main():
    dry_run = "--dry-run" in sys.argv
    force = "--force" in sys.argv
    cfg = load_config()
    now = datetime.datetime.now()
    date_key = now.strftime("%Y-%m-%d")
    if not os.path.isdir(OUT_DIR):
        os.makedirs(OUT_DIR)
    html_path = os.path.join(OUT_DIR, "%s-热点速览.html" % date_key)
    if os.path.exists(html_path) and not force:
        log("今天已生成 %s，跳过（加 --force 可强制重生成）" % html_path)
        return

    domestic, intl = collect(cfg)
    domestic, intl = classify(domestic, intl)
    log("分类后：国内 %d 条 / 国际 %d 条" % (len(domestic), len(intl)))
    if len(domestic) < 6 or len(intl) < 4:
        raise RuntimeError("新闻源可用条目过少，本次终止")

    picked = call_llm(cfg, domestic, intl)
    if picked:
        dom = merge_fill(picked["domestic"], domestic, 12, "综合报道")
        itl = merge_fill(picked["intl"], intl, 8, "综合报道")
        guide = [d["title"] for d in (dom[:4] + itl[:2])]
        log("使用大模型生成内容（国内 %d / 国际 %d）" % (len(dom), len(itl)))
    else:
        dom = fallback(domestic, 12, "综合报道")
        itl = fallback(intl, 8, "综合报道")
        guide = [d["title"] for d in (dom[:4] + itl[:2])]
        log("未启用大模型，使用原始标题+摘要（国内 %d / 国际 %d）" % (len(dom), len(itl)))

    weekday = "周" + "一二三四五六日"[now.weekday()]
    issue = (now.date() - datetime.date(2026, 11, 5)).days + 1
    cn_date = "%d年%d月%d日" % (now.year, now.month, now.day)
    date_line = "%s · %s · 第 %d 期" % (cn_date, weekday, issue)
    html = render(cfg, date_line, guide, dom, itl)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    log("HTML 已生成：%s（%d 字符）" % (html_path, len(html)))

    if dry_run:
        log("dry-run 模式，跳过推送")
        return
    title = "每日热点速览 · %s" % cn_date
    publish(cfg, title, html_path)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        log("ERROR: %s" % exc)
        sys.exit(1)
