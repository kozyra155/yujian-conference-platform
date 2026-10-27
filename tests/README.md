# 测试与验收脚本

所有命令默认在项目根目录运行。测试只在开发验收时使用，日常启动网站不需要执行它们。

## 目录

- `backend/`：Python 后端、接口、权限、支付和配置检查，也包含本机服务可用性检查。
- `browser/`：Playwright 浏览器验收及 `inspect_*.cjs` 页面诊断。
- 前端错误消息单元测试继续与前端代码放在一起：`frontend/apiErrors.test.mjs`。

浏览器脚本通过自身位置定位项目根目录，Docker 命令仍从根目录执行；私有账号/注册预览文件仍在原位置，截图和报告沿用原路径。`inspect_*` 仅供排查页面，不是启动步骤。

## 不写业务数据的检查

```powershell
# 本机 SMTP 配置单元测试，不连接邮箱或发送邮件。
D:/python/python.exe -m unittest discover -s tests/backend -p test_smtp_config.py
node --test frontend/apiErrors.test.mjs

# 使用实际 CSS 检查手机登录按钮；不依赖网站、不创建账号。
node tests/browser/verify_complete_mobile.cjs

# 要求 Docker 和网站已经启动，只读检查服务和页面。
D:/python/python.exe tests/backend/verify_service_recovery.py
```

## 容器内后端检查

其余依赖 Indico 的 Python 脚本在 `indico-web` 容器执行。宿主机源路径与容器临时路径不同：

```powershell
docker compose cp tests/backend/verify_review_regressions.py indico-web:/tmp/verify_review_regressions.py
docker compose exec -T indico-web /opt/indico/.venv/bin/python /tmp/verify_review_regressions.py
```

可按变更选择以下脚本；它们不是一个可以全部批量运行的测试套件。

| 改动 | 后端检查 | 浏览器检查 |
| --- | --- | --- |
| 支付、订单、状态和时间精度 | `tests/backend/verify_review_regressions.py`、`tests/backend/verify_payments.py` | `node tests/browser/verify_payments_ui.cjs` |
| 基本信息与首页内容 | `tests/backend/metadata_selfcheck.py`、`tests/backend/metadata_api_selfcheck.py`、`tests/backend/verify_feedback_content.py` | `node tests/browser/verify_feedback_metadata_ui.cjs`、`node tests/browser/verify_feedback_editor.cjs` |
| 倒计时 | `tests/backend/verify_countdown.py` | `node tests/browser/verify_countdown_ui.cjs` |
| 会议检索 | `tests/backend/verify_conference_search.py` | `node tests/browser/verify_event_filters.cjs` |
| 合作意向登记 | `tests/backend/verify_interests.py` | `node tests/browser/verify_interests_ui.cjs` |
| 账号与邮箱验证 | `tests/backend/verify_conference_accounts.py`、`tests/backend/verify_conference_accounts_feedback.py` | `node tests/browser/verify_conference_accounts_ui.cjs` |

## 运行边界

- 先阅读脚本和对应 `docs/` 验收说明。早期 `verify_browser`、`verify_builder_browser` 等会使用既有演示账号或保留演示会议；不要盲目运行所有脚本。
- 新回归脚本创建唯一标识的临时账号和会议，并在结束时清理可见记录；不能修改会议 22、61、171 或真实业务数据。
- 业务自动化使用内存邮件和模拟支付，不代表真实邮件送达或真实商户支付验收。`tests/backend/verify_smtp_runtime.py` 是单独的连接认证检查，会访问实际 SMTP 服务器，但不发送邮件。
- 浏览器使用本机现有 Playwright：`D:/playwright-demo/node_modules/playwright`；换机器需要调整该依赖路径。旧脚本可能依赖本地演示账号、预览 JSON 或此前后端生成的结果，这些私有文件不随仓库提供。
- 运行结果、注册令牌、密码、Cookie 和截图报告不应进入 Git；保留现有 `.gitignore` 规则。
