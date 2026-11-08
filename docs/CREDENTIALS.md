# 密钥与配置获取指南

> 时间久了容易忘，这里把每个密钥「从哪拿、填到哪、注意什么」写清楚。
> 所有真实密钥只存在服务器 `/opt/daily-news/config.json`（权限 600），**不入 Git 仓库**。

## 一、速查表

| 配置项 | 从哪获取 | 填到哪 | 备注 |
|---|---|---|---|
| `appid` | 公众号后台 → 设置与开发 → 账号设置（页面底部） | `config.json` | `wx` 开头，18 位，不会变 |
| `secret`（AppSecret） | 微信开发者平台 → 我的业务 → 公众号 → 基础信息 → 开发密钥 → 重置 | `config.json` | **只显示一次**，重置后旧值立即失效 |
| `llm.api_key` | 腾讯云 TokenHub 控制台 → API Key 管理 → 创建 | `config.json` | `sk-` 开头 |
| `llm.base_url` | 固定值 | `https://tokenhub.tencentmaas.com/v1` | 少写 `https://` 会直接报错 |
| IP 白名单 | 公众号后台 → 设置与开发 → 基本配置 → IP 白名单 → 修改 | 微信侧，不在配置文件 | **服务器公网 IP**，不是本机 IP |

## 二、AppID 与 AppSecret

**AppID**（不会变，可长期保存）

1. 浏览器打开 `mp.weixin.qq.com`，管理员微信扫码登录
2. 左下角「设置与开发」→「账号设置」
3. 页面下方「公众号信息」里就是 AppID（`wx` 开头）

**AppSecret**（可重置，务必及时保存）

1. 打开 `developers.weixin.qq.com/platform`（微信开发者平台）
2. 「我的业务」→ 找到你的公众号 → 填入 AppID 完成认领
3. 进入该公众号「基础信息」→「开发密钥」区域
4. 点「重置」，管理员扫码验证，生成新的 AppSecret
5. **只显示这一次**，立刻复制到 `config.json`

⚠️ 重置会让旧密钥**立即失效**。如果还有其他服务（如第三方排版工具）正在用同一个 AppSecret，记得同步更新。

## 三、大模型 API Key（TokenHub）

1. 登录腾讯云控制台，进入 **TokenHub**（`tokenhub.tencentmaas.com`，或腾讯云控制台搜索「TokenHub / 大模型知识引擎」）
2. 「模型广场」开通需要的模型，新用户可领免费额度（常见为 100 万 tokens，有效期 1 年）
3. 「API Key 管理」→ 选择地域 → 「创建 API Key」→ 复制（`sk-` 开头）
4. 填入 `config.json` 的 `llm.api_key`

**可选模型说明**（`model_chain` 为降级顺序，前一个失败自动换下一个）：

| 模型 | 实测表现 | 建议位置 |
|---|---|---|
| `mimo-v2.6-flash` | 快，JSON 稳定 | 首选 |
| `deepseek/deepseek-flash` | 约 50 秒，偶尔输出截断（已加容错） | 次选 |
| `glm-5.3` | 可用，稍慢 | 备选 |
| `hy4` | 推理型，20 条长任务易超时 | 兜底 |
| `hunyuan-lite` | **TokenHub 无此模型**（会 400） | 不要配 |
| `kimi-k3.1-pro-highspeed` | 实测 400 | 不要配 |

## 四、IP 白名单

1. 公众号后台 → 设置与开发 → **基本配置** → 公众号开发信息 → **IP 白名单** → 修改
2. 填入**调用方公网 IP**（云服务器就是它的固定公网 IP），一行一个，不要带空格或 `/32`
3. 点确定后**管理员扫码确认**，页面提示保存成功才生效
4. 验证是否生效：`curl -s "https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid=APPID&secret=SECRET"`，返回 `access_token` 即通

报错对照：

| 错误码 | 含义 | 处理 |
|---|---|---|
| `40164` | IP 不在白名单 | 按上面步骤加 IP |
| `40013` | AppID 错误 | 检查 `appid` |
| `40125` | AppSecret 错误或已重置 | 重新获取并更新 |
| `48001` | 无该接口权限 | 账号未认证，缺少发布权限（草稿接口不受影响） |

## 五、密钥保管建议

- `config.json` 权限设为 `600`：`chmod 600 /opt/daily-news/config.json`
- 备份到密码管理器（1Password / KeePass），不要只存在聊天记录里
- 怀疑泄露：立即在开发者平台重置 AppSecret，并更新服务器配置
- 本仓库只提交 `config.example.json`（占位值），`.gitignore` 已排除真实配置
