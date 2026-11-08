# 部署与迁移手册

> 换服务器 / 重装系统时，照着这份文档从零重建，约 15 分钟。

## 一、前置条件

| 条件 | 说明 |
|---|---|
| 服务器 | Linux（实测 Alibaba Cloud Linux 3 / Python 3.6.8 可用，Ubuntu 20.04+ 亦可） |
| Python | 3.6 及以上，**不需要安装任何第三方库**（全部标准库） |
| 固定公网 IP | 必须，且需加入公众号 IP 白名单（家庭宽带 IP 会变，不推荐） |
| 时区 | 服务器时区设为 `Asia/Shanghai`，否则 8 点会错位 |

## 二、从零部署（新服务器）

```bash
# 1. 建目录并放文件
mkdir -p /opt/daily-news/{out,logs}
# 把 news_bot.py、page-template.html、cover.jpg 上传到 /opt/daily-news/
# 注意：page-template.html 必须与 news_bot.py 同目录；缺失时脚本会回退内置版式（样式会变旧）

# 2. 生成配置（照 config.example.json 填真实值）
cp config.example.json /opt/daily-news/config.json
vi /opt/daily-news/config.json          # 填 appid / secret / llm.api_key
chmod 600 /opt/daily-news/config.json

# 3. 校准时区
timedatectl set-timezone Asia/Shanghai

# 4. 注册定时任务
bash setup_cron.sh                      # 写入 /etc/cron.d/daily-news，每天 08:00
systemctl is-active crond                # 应为 active

# 5. 干跑验证（不推送）
cd /opt/daily-news && python3 news_bot.py --dry-run --force

# 6. 真实推送验证
cd /opt/daily-news && python3 news_bot.py --force
```

成功标志：日志出现 `草稿推送成功 media_id=...`，公众号后台草稿箱能看到文章。

## 三、迁移检查清单

换服务器时逐项确认，漏一项就跑不通：

- [ ] 新服务器公网 IP 已加入公众号 IP 白名单（**最关键**，忘了必报 40164）
- [ ] `config.json` 里 `appid` / `secret` / `llm.api_key` 已填**真实值**（不是 example 占位）
- [ ] `base_url` 带 `https://` 前缀
- [ ] `cover.jpg` 已上传（草稿必须有封面）
- [ ] 时区为 Asia/Shanghai
- [ ] crond 服务处于 active
- [ ] 跑过 `--dry-run` 确认新闻源可访问
- [ ] 旧服务器的 cron **已删除**，避免两边同时推送造成重复草稿

旧服务器下线前：

```bash
rm -f /etc/cron.d/daily-news && echo "旧机 cron 已移除"
```

## 四、日常运维

```bash
# 查看今天的日志
tail -30 /opt/daily-news/logs/$(date +%F).log

# 手动补发（当天没跑或跑失败）
cd /opt/daily-news && python3 news_bot.py --force

# 只生成不推送（排查内容问题）
cd /opt/daily-news && python3 news_bot.py --dry-run --force

# 查看定时任务
cat /etc/cron.d/daily-news
```

## 五、故障排查

| 现象 | 原因 | 处理 |
|---|---|---|
| `40164 invalid ip` | 白名单没加/加错 | 添加服务器公网 IP 并**扫码确认** |
| `40125 invalid appsecret` | 密钥错或已重置 | 重新获取 AppSecret 并更新配置 |
| `48001 api unauthorized` | 账号未认证，无发布权限 | 只到草稿箱属正常，见 README |
| `新闻源可用条目过少` | RSS 停更或网络不通 | 跑 `probe_feeds` 类脚本确认源，或更换源 |
| 所有模型都失败 | Key 失效 / 额度耗尽 | 日志会写具体错误，去 TokenHub 查额度 |
| 草稿箱出现重复文章 | 旧机 cron 未删 / 本地定时任务同时在跑 | 只保留一处调度 |
| 文章有灰框竖线 | 表格未写 `border:none` | 见 README「踩坑记录」第 3 条 |

## 六、扩展：接搜索 API 提升新闻源质量

当前 RSS 源只有 3 个有效（中新网滚动/国际、界面新闻）。若要更丰富的来源：

1. 注册搜索 API（如博查 Bocha，`bochaai.com`，按次计费约 0.03 元/次）
2. 在 `news_bot.py` 的 `collect()` 中，用搜索接口替换或补充 RSS 抓取
3. 其余环节（去重、分类、模型改写、排版、推送）无需改动

## 七、Git 与仓库

```bash
# 本机推送 GitHub 前必须先写入仓库级代理配置
bash scripts/setup-git-proxy.sh

# 之后正常提交
git add -A && git commit -m "..." && git push origin main
```

仓库地址：`https://github.com/kgchaos1/daily-news.git`
提交身份：`kgchaos1 <kgchaos1@users.noreply.github.com>`（不使用公司邮箱）
