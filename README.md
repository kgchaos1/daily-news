# 每日热点速览 · 公众号自动化出刊

每天自动抓取国内外热点新闻，用大模型筛选改写，按公众号兼容版式排版，推送到微信公众号草稿箱。

## 架构

```
cron 08:00
   │
   ├─ 抓取 RSS 新闻源（中新网 / 界面新闻）
   ├─ 48 小时新鲜度过滤 + 去重 + 国内/国际分类
   ├─ 大模型挑选 20 条（国内 12 / 国际 8）并生成摘要
   ├─ 渲染公众号兼容 HTML（表格布局 + em 单位 + 纯色兜底）
   └─ 微信官方 API → 草稿箱
```

两种运行方式：

| 方式 | 位置 | 说明 |
|---|---|---|
| 云端（推荐） | `cloud/` | 阿里云 Linux + cron，电脑无需开机，固定公网 IP 白名单 |
| 本地 | `weixin/` | 手动或由 WorkBuddy 定时任务触发，依赖 PC 开机 |

## 目录结构

```
cloud/
  news_bot.py          云端全流程脚本（Python 3.6+，仅标准库）
  config.example.json  配置模板（复制为 config.json 后填密钥）
  probe_feeds*.py      新闻源可用性探测工具
  probe_models.py      大模型可用性与模型列表探测
  setup_cron.sh        注册 /etc/cron.d 定时任务
weixin/
  publish_draft.py     本地建草稿脚本（支持 --publish 调发布接口）
  cover.jpg            公众号封面（900×383）
news/
  TEMPLATE.html        20 条版式（第一版，固定 px）
  TEMPLATE_V2.html     跨端兼容版式（表格布局 + em 单位，推荐）
avatars/
  方案1_极简报纸环.png 等 4 款圆形头像
```

## 部署

```bash
# 1. 服务器准备
mkdir -p /opt/daily-news/{out,logs}
cp news_bot.py config.json cover.jpg /opt/daily-news/
chmod 600 /opt/daily-news/config.json

# 2. 填写 config.json：appid / secret / llm.api_key
# 3. 注册定时任务
bash setup_cron.sh          # 每天 08:00 执行
# 4. 手动验证
cd /opt/daily-news && python3 news_bot.py --dry-run --force   # 只生成不推送
cd /opt/daily-news && python3 news_bot.py --force             # 生成并推草稿箱
```

## 关键约束与踩坑记录

**1. IP 白名单（最容易翻车）**
微信要求调用方公网 IP 在公众号后台白名单内，否则返回 `40164`。家庭宽带 IP 会变，所以推荐部署在固定 IP 的云服务器上，白名单加一次即可。

**2. 国内 RSS 大面积停更**
实测：新浪 RSS 停在 2018 年、人民网停在 2025-06、36氪/联合早报/环球网解析为 0 条、BBC 中文与澎湃在境内服务器不可达。目前稳定可用的只有中新网（滚动/国际）与界面新闻。若需更丰富的来源，建议接搜索 API（博查/混元联网搜索）。

**3. 微信编辑器会给表格画边框**
用 `<table>` 做兼容布局时，只在 table 上写 `border="0"` 无效，必须给**每个** `td` 的内联样式显式写 `border:none`，否则每条新闻会出现灰框和竖线。

**4. 模型选择**
- 推理型模型（如 hy4）在 20 条长任务上思考时间超过 3 分钟，容易超时，只作兜底；
- 首选快而稳的 `deepseek/deepseek-flash`（实测 50 秒完成，JSON 输出稳定）；
- 脚本内置模型降级链，任一模型失败自动换下一个，全部失败回退到纯 RSS 模式，保证不断更。

**5. 自动发表做不到（账号资质限制）**
未认证公众号没有 `freepublish` 权限（返回 `48001`），API 只能到草稿箱，最后一步「发表」需人工点击，或完成微信认证后启用 `--publish`。

## 安全

- `config.json` 含 AppSecret 与 API Key，已在 `.gitignore` 中排除，仓库只保留 `config.example.json`；
- 服务器建议改用 SSH 密钥登录并关闭密码登录。

## 版本

- v1：10 条版式，固定 px 缩进
- v2：20 条 + 跨端兼容（表格布局、em 单位、纯色兜底、`-webkit-` 前缀）
- v3：迁移云端，接入大模型筛选改写，模型降级链
