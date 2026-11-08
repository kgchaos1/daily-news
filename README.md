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
  setup_cron.sh        注册 /etc/cron.d 定时任务
weixin/
  publish_draft.py     本地建草稿脚本（支持 --publish 调发布接口）
  cover.jpg            公众号封面（900×383）
news/
  page-template.html   文章版式（唯一事实源：改样式只改这个文件）
avatars/
  方案1_极简报纸环.png 等 4 款圆形头像
docs/
  CREDENTIALS.md       密钥从哪获取、填到哪、报错对照
  DEPLOY.md            部署与服务器迁移手册
scripts/
  setup-git-proxy.sh   新仓库一键写入代理/身份配置
```

## 改样式怎么改

`news/page-template.html` 是**唯一事实源**，`news_bot.py` 只是往里填内容：

| 占位符 | 含义 |
|---|---|
| `{{DATE_LINE}}` | 日期行，如 `2026年11月9日 · 星期一 · 第 4 期` |
| `{{GUIDE}}` | 今日导读（6 条，`<br>` 分隔） |
| `{{DOMESTIC}}` | 国内 12 条展开后的 HTML |
| `{{INTL}}` | 国际 8 条展开后的 HTML |

单条新闻的版式由文件末尾的 `<!-- DOM_ITEM_START -->…<!-- DOM_ITEM_END -->` 与
`<!-- INTL_ITEM_START -->…<!-- INTL_ITEM_END -->` 两块定义，块内可用
`{{IDX}}` `{{TITLE}}` `{{SUMMARY}}` `{{SOURCE}}`。这两块只在渲染时被提取，不会出现在成品里。

改完样式：
```bash
scp news/page-template.html root@8.133.220.164:/opt/daily-news/   # 云端 8:00 自动生效
python3 cloud/news_bot.py --dry-run --force                       # 本地先看效果
```
若服务器上找不到模板文件，`news_bot.py` 会自动回退到内置版式（`render_builtin`），不会出空白稿。

## 部署

```bash
# 1. 服务器准备
mkdir -p /opt/daily-news/{out,logs}
cp news_bot.py config.json cover.jpg page-template.html /opt/daily-news/
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
TokenHub 实测（**没有 `hunyuan-lite`，`kimi-k3.1-pro-highspeed` 返回 400，两者都不要配**）：

| 模型 | 实测 | 位置 |
|---|---|---|
| `mimo-v2.6-flash` | 快，JSON 稳定 | 首选 |
| `deepseek/deepseek-flash` | 约 50 秒，偶尔截断（已加容错修复） | 次选 |
| `glm-5.3` | 可用，稍慢 | 备选 |
| `hy4` | 推理型，20 条长任务易超时 | 兜底 |

脚本内置 `model_chain` 降级链，任一模型失败自动换下一个；对截断的 JSON 有 `parse_json_loose()` 补齐修复；全部失败回退纯 RSS 模式，保证不断更。

**5. 自动发表做不到（账号资质限制）**
未认证公众号没有 `freepublish` 权限（返回 `48001`），API 只能到草稿箱，最后一步「发表」需人工点击，或完成微信认证后启用 `--publish`。

更多细节见 [docs/CREDENTIALS.md](docs/CREDENTIALS.md)（密钥获取）与 [docs/DEPLOY.md](docs/DEPLOY.md)（部署迁移）。

## 在这台机器上推送其他 GitHub 仓库

本机 GitHub 直连超时，系统代理对 Git 不生效，需在**每个仓库**写入下面 5 条仓库级配置（不污染全局）：

```bash
git config user.name "kgchaos1"
git config user.email "kgchaos1@users.noreply.github.com"
git config http.proxy "http://127.0.0.1:7897"
git config https.proxy "http://127.0.0.1:7897"
git config http.sslBackend schannel   # 不加会 OpenSSL 握手失败
```

或直接用脚本：`cd <仓库根目录> && bash scripts/setup-git-proxy.sh`

## 安全

- `config.json` 含 AppSecret 与 API Key，已在 `.gitignore` 中排除，仓库只保留 `config.example.json`；
- 提交身份固定为 `kgchaos1 <kgchaos1@users.noreply.github.com>`，仅写入仓库级配置，不使用任何公司邮箱；
- 服务器建议改用 SSH 密钥登录并关闭密码登录。

## 版本

- v1：10 条版式，固定 px 缩进
- v2：20 条 + 跨端兼容（表格布局、em 单位、纯色兜底、`-webkit-` 前缀）
- v3：迁移云端，接入大模型筛选改写，模型降级链
