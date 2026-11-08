# -*- coding: utf-8 -*-
"""第二轮新闻源探测：中新网各频道 + 其他站点"""
import re
import urllib.request

FEEDS = [
    ("中新网-滚动", "https://www.chinanews.com.cn/rss/scroll-news.xml"),
    ("中新网-国内", "https://www.chinanews.com.cn/rss/china-news.xml"),
    ("中新网-财经", "https://www.chinanews.com.cn/rss/finance-news.xml"),
    ("中新网-社会", "https://www.chinanews.com.cn/rss/society-news.xml"),
    ("中新网-国际", "https://www.chinanews.com.cn/rss/world.xml"),
    ("中新网-国际2", "https://www.chinanews.com.cn/rss/gj.xml"),
    ("中国日报-中文", "https://cn.chinadaily.com.cn/rss/china_rss.xml"),
    ("中国日报-国际", "https://cn.chinadaily.com.cn/rss/world_rss.xml"),
    ("虎嗅", "https://www.huxiu.com/rss/0.xml"),
    ("少数派", "https://sspai.com/feed"),
    ("36氪", "https://36kr.com/feed"),
    ("澎湃-feedx", "https://feedx.net/rss/thepaper.xml"),
    ("财新-财新网", "https://www.caixin.com/rss/all.xml"),
    ("界面新闻", "https://a.jiemian.com/index.php?m=article&a=rss"),
]

for name, url in FEEDS:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        raw = urllib.request.urlopen(req, timeout=15).read()
        text = raw.decode("utf-8", "replace")
        items = text.count("<item")
        entries = text.count("<entry")
        dates = re.findall(r"<pubDate>(.*?)</pubDate>", text)[:2] or re.findall(r"<published>(.*?)</published>", text)[:2]
        print("OK   %-14s bytes=%-7d items=%-4d entry=%-3d dates=%s" % (name, len(text), items, entries, dates))
    except Exception as exc:
        print("FAIL %-14s %s" % (name, str(exc)[:50]))
