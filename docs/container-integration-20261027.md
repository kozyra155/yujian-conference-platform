# 2026-10-27 容器集成测试

测试目录整理后，在现有 `yujian-indico-v1` 环境重跑。使用现有镜像启动六个服务，没有重新构建镜像或初始化数据库。

## 后端：19 组全部通过

以下脚本均从 `tests/backend/` 复制到 `indico-web` 临时目录，使用应用虚拟环境执行，退出码均为 0。

| 范围 | 脚本 |
| --- | --- |
| 元数据 | `metadata_selfcheck.py`、`metadata_api_selfcheck.py` |
| 建站与完整会议首页 | `verify_site_builder.py`、`verify_complete_site.py`、`verify_complete_rendering.py` |
| 外观与内容 | `verify_appearance_api.py`、`verify_appearance_rendering.py`、`verify_feedback_content.py` |
| 检索、倒计时与合作意向 | `verify_conference_search.py`、`verify_countdown.py`、`verify_interests.py` |
| 账号与邮箱验证 | `verify_conference_accounts.py`、`verify_conference_accounts_feedback.py` |
| 报名、投稿与工作台 | `verify_complete_business.py`、`verify_business_workspace.py`、`verify_business_lifecycle.py`、`verify_native_business.py` |
| 支付与审查回归 | `verify_payments.py`、`verify_review_regressions.py` |

`verify_review_regressions.py` 首轮触发宿主运行器的 180 秒超时。确认没有遗留测试进程或数据库锁等待后，单独重跑，10 项测试全部通过，用时 180.244 秒。不能把首轮超时记为断言失败，也不能把它省略为首次通过。

应用测试期间使用内存邮件与模拟支付渠道，没有执行真实付款或退款。

## 浏览器：两组未通过

- `node tests/browser/verify_native_business_ui.cjs`：首次导航到临时会议的报名管理页时超过 15 秒，尚未执行页面布局断言。
- `node tests/browser/verify_payments_ui.cjs`：导航到登录页时超过 12 秒，尚未执行支付界面断言。

独立浏览器探针也发生导航超时；普通 HTTP 请求访问登录页、全局 JS、公共 JS 包和门户 JS 均返回 200。浏览器探针能收到部分页面与资源的 200 响应，但尚未确定导航超时的根因，不能据此认定浏览器业务流程通过，也不能认定是支付业务逻辑失败。

检查中另发现原生业务预览夹具将 Cookie 域名固定为 `localhost`。已改为读取 Indico 的 `BASE_URL` 主机名，并在浏览器脚本中增加 Cookie 对当前站点生效的断言。此修复仅涉及测试夹具，不改变应用登录逻辑；导航超时问题仍需单独处理。

修复后额外在容器运行预览分支，18 个原生业务页面的后端检查通过，并确认三个角色的 Cookie 域名均与配置站点一致。该检查不等同于浏览器导航和布局断言通过。

## 服务与数据

`tests/backend/verify_service_recovery.py` 本轮通过：六个服务运行、自动重启策略符合配置，localhost 入口、内网首页、登录页和会议 61 返回 200。

两组浏览器测试结束后，数据库快照与运行前一致：7 场可见会议、5 个可见用户；原有会议、会议设置、报名表、报名记录、用户五类表的原始记录指纹一致。会议 22、61、171 保持原状，临时账号与会议已清理可见记录。测试使用软删除，不清空数据库或重置序列。

原始日志与快照只保存在本机仓库外的 `../output/integration-20261027/`，不提交注册令牌、Cookie、账号或运行配置。

## 未覆盖

未盲目运行全部历史浏览器脚本；未验收真实邮箱送达、真实商户收退款、其他实体电脑访问或从零构建部署。后端通过与浏览器未通过分别记录，不能视为完整 UI 验收通过。
