# -*- coding: utf-8 -*-
"""
微信公众号草稿发布脚本（仅用 Python 标准库，无第三方依赖）
用法: python publish_draft.py <文章标题> <正文html文件路径>
流程: 获取 access_token -> 上传封面图 -> 新建草稿
"""
import json
import os
import sys
import urllib.request
import urllib.parse

BASE = "https://api.weixin.qq.com"
HERE = os.path.dirname(os.path.abspath(__file__))


def load_config():
    with open(os.path.join(HERE, "config.json"), "r", encoding="utf-8") as f:
        return json.load(f)


def http_post_json(url, data):
    req = urllib.request.Request(
        url,
        data=json.dumps(data, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def http_get(url):
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def check(resp, step):
    if resp.get("errcode") not in (None, 0):
        print("[FAIL] %s: %s" % (step, json.dumps(resp, ensure_ascii=False)))
        sys.exit(1)
    print("[OK] %s" % step)
    return resp


def get_access_token(cfg):
    url = "%s/cgi-bin/token?grant_type=client_credential&appid=%s&secret=%s" % (
        BASE, cfg["appid"], cfg["secret"])
    resp = http_get(url)
    if "access_token" not in resp:
        print("[FAIL] 获取access_token: %s" % json.dumps(resp, ensure_ascii=False))
        if resp.get("errcode") == 40164:
            print("提示: 出口IP不在白名单，请在公众号后台 设置与开发->基本配置->IP白名单 添加当前IP")
        sys.exit(1)
    print("[OK] 获取access_token")
    return resp["access_token"]


def upload_cover(token, cfg):
    """上传永久素材封面图，返回 thumb_media_id"""
    cover_path = os.path.join(HERE, cfg.get("cover_image", "cover.jpg"))
    if not os.path.exists(cover_path):
        print("[FAIL] 封面图不存在: %s" % cover_path)
        sys.exit(1)
    boundary = "----wb%s" % os.urandom(8).hex()
    filename = os.path.basename(cover_path)
    with open(cover_path, "rb") as f:
        file_data = f.read()
    body = (
        ("--%s\r\n" % boundary).encode()
        + ('Content-Disposition: form-data; name="media"; filename="%s"\r\n' % filename).encode()
        + b"Content-Type: image/jpeg\r\n\r\n"
        + file_data
        + ("\r\n--%s--\r\n" % boundary).encode()
    )
    url = "%s/cgi-bin/material/add_material?access_token=%s&type=image" % (BASE, token)
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "multipart/form-data; boundary=%s" % boundary)
    with urllib.request.urlopen(req, timeout=60) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    check(result, "上传封面图")
    return result["media_id"]


def create_draft(token, cfg, title, html_path):
    with open(html_path, "r", encoding="utf-8") as f:
        content = f.read()
    thumb_media_id = upload_cover(token, cfg)
    url = "%s/cgi-bin/draft/add?access_token=%s" % (BASE, token)
    article = {
        "articles": [{
            "title": title,
            "author": cfg.get("author", ""),
            "digest": "",
            "content": content,
            "thumb_media_id": thumb_media_id,
            "need_open_comment": 1,
            "only_fans_can_comment": 0,
        }]
    }
    resp = check(http_post_json(url, article), "新建草稿")
    print("[DONE] 草稿已推送到公众号草稿箱, media_id=%s" % resp.get("media_id"))
    return resp.get("media_id")


def publish_draft(token, media_id):
    """调用发布接口 freepublish/submit：把草稿正式发表到账号主页。
    注意：发布不占用每日群发次数，但不会向粉丝推送提醒消息。"""
    url = "%s/cgi-bin/freepublish/submit?access_token=%s" % (BASE, token)
    resp = http_post_json(url, {"media_id": media_id})
    if resp.get("errcode") not in (None, 0):
        print("[FAIL] 发布草稿: %s" % json.dumps(resp, ensure_ascii=False))
        code = resp.get("errcode")
        if code == 48001:
            print("提示: 该账号没有发布接口权限，通常需要已认证的订阅号/服务号并开通发布能力")
        elif code == 53404:
            print("提示: 账号曾被处罚，暂不可使用发布能力")
        elif code == 53503:
            print("提示: 发布内容与草稿不一致或草稿已发布")
        sys.exit(2)
    print("[DONE] 已提交发布, publish_id=%s" % resp.get("publish_id"))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    do_publish = "--publish" in sys.argv
    if len(args) < 2:
        print("用法: python publish_draft.py <标题> <正文html路径> [--publish]")
        print("  --publish  建完草稿后立即调用发布接口正式发表（不占用群发次数）")
        sys.exit(1)
    cfg = load_config()
    if not cfg.get("secret") or "填入" in cfg.get("secret", ""):
        print("[FAIL] 请先在 config.json 中填入 AppSecret")
        sys.exit(1)
    token = get_access_token(cfg)
    media_id = create_draft(token, cfg, args[0], os.path.abspath(args[1]))
    if do_publish:
        publish_draft(token, media_id)


if __name__ == "__main__":
    main()
