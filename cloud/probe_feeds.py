# -*- coding: utf-8 -*-
"""探测新闻源可用性与新鲜度"""
import re
import urllib.request

FEEDS = [
    ("中新网滚动", "https://www.chinanews.com.cn/rss/scroll-news.xml"),
    ("中新网国际", "http://www.chinanews.com.cn/rss/world-news.xml"),
    ("新浪国内", "https://rss.sina.com.cn/news/china/focus15.xml"),
    ("新浪国际", "https://rss.sina.com.cn/news/world/focus15.xml"),
    ("新浪社会", "https://rss.sina.com.cn/news/society/focus15.xml"),
    ("36氪", "https://36kr.com/feed"),
    ("联合早报国际", "https://www.zaobao.com.sg/rss/realtime/world"),
    ("人民网国际", "http://www.people.com.cn/rss/world.xml"),
]

for name, url in FEEDS:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        raw = urllib.request.urlopen(req, timeout=15).read()
        text = raw.decode("utf-8", "replace")
        items = text.count("<item")
        dates = re.findall(r"<pubDate>(.*?)</pubDate>", text)[:2]
        titles = re.findall(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", text)[1:3]
        print("OK   %-12s bytes=%-7d items=%-4d dates=%s" % (name, len(text), items, dates))
        for t in titles:
            print("       - %s" % t[:36])
    except Exception as exc:
        print("FAIL %-12s %s" % (name, str(exc)[:60]))
