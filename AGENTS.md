# 项目协作约定

适用范围：本目录及子目录。更新日期：2026-10-27。先阅读 README.md、tests/README.md 与对应 docs 验证记录，区分当前实现、历史验收和未验证项。

## 项目与环境

- 遇见科技会议服务平台：Indico 3.3.13、Python 扩展、Vue 3 / Element Plus、PostgreSQL 16、Redis 7、Nginx。
- 应用项目根目录为本目录；本机路径 `D:/works/yujian-conference-design/indico-demo`。上游参考源码在 `../indico-source`，容器参考在 `../indico-containers`；定制优先写入本项目，不直接修改上游。
- Compose 项目名固定 `yujian-indico-v1`。六个服务：indico-web、indico-celery、indico-celery-beat、indico-postgres、indico-redis、indico-nginx。不要另起不同项目名连接另一套空数据卷。
- 规范站点地址 `http://192.168.2.36:12880/`；localhost/127.0.0.1 跳转到此地址。地址变更需同步 Compose、Nginx、私有配置、测试与防火墙。
- 宿主机 Python：`D:/python/python.exe`；应用 Python：`/opt/indico/.venv/bin/python`；本机 Playwright：`D:/playwright-demo/node_modules/playwright`。浏览器测试脚本中的绝对路径换机器后需要调整。

## 源码与生成文件

- `worker/extension/yujian_site/`：授权、建站、内容、会议元数据、检索、账号上下文、合作意向、支付与公开展示；复用原生 Indico 生命周期和权限。
- `frontend/src/`：工作台组件；`portal/`：门户及会议展示资源；`customization/templates/`：原生模板扩展。
- `portal/ui-dist/` 由 `frontend` 中 `npm run build` 生成并随源码提交，不手工编辑生成文件。依赖不全时先 `npm ci`。
- `portal/events.html` 由 `build_events.py` 组装，`worker/extension/yujian_site/templates/builder.html` 由 `build_builder.py` 组装。共享门户头尾变更需重建这两处。
- Python/模板更新后重启 Web、Celery、Beat；应用重新创建或地址变化后重启 Nginx。Nginx 配置更新先 `nginx -t`，再 reload 或重新创建。

## 数据与密钥

- `.env`、`indico.conf`、`smtp-settings.json`、`demo-accounts.json`、商户配置与密钥均为私有文件。不要输出、提交、上传或放入示例；只提交无真实值的 `.example` 文件。
- 注册预览链接、会话 Cookie、报名令牌、运行日志、验收 JSON、数据库和附件备份不进入 Git。检查暂存区后再提交推送。
- PostgreSQL 数据位于 `postgres-data` 卷，上传附件位于 `archive` 卷。禁止把 `docker compose down -v`、清卷、重新 seed 或数据库重置当作启动/排障步骤。
- 本机 Docker 数据在 `D:/DockerData/disk/docker_data.vhdx`，WSL 系统盘在 `D:/DockerData/main/ext4.vhdx`；迁移备份在 `D:/DockerBackups/migration-20261022-091735/`。C 盘旧 `wsl/disk` 路径是映射，不能递归清理；不要在 Docker 运行时移动 VHDX。
- 验证不得修改已有会议 22、61、171 或真实账号/报名/订单。创建唯一命名的临时数据，在 finally/tearDown 中清理可见记录；不要为低影响文档改动创建业务数据。

## 业务约束

- 保留 CSRF、登录验证、原生完整管理权限、草稿/撤回与锁定规则；不能只依赖前端隐藏按钮。图片必须属于本会议，富文本和链接继续经过后端校验。
- 内容保存使用事件行锁与 revision；基本信息使用 revision 和原生字段 fingerprint 防覆盖。不得删除并发保护；未修改的富文本、联系方式和时间精度应保留。
- 发布后保存内容会立即改变公开网站；目前没有独立草稿版本，不应声称已实现。
- 已有财务订单的报名不能在原生页面撤销、重置、改价或编辑。支付/退款写入前取得报名行锁，保留流水去重、金额校验和审计。
- 支付过期不能直接覆盖旧交易：先验签查单，确认支付则登记到账；确认关闭后才能换支付单号。公司订单号保持稳定；查单/关单不确定时保留原记录。
- `payment_exception` 表示已收到合法渠道到账通知，但报名状态或金额失配。保留记录、不自动批准报名或开票；允许公司财务按实际退款结果登记全额退款。
- SMTP 可真实发信，测试必须覆盖为内存后端：`EMAIL_BACKEND='indico.vendor.django_mail.backends.locmem.EmailBackend'`、`SMTP_USE_CELERY=False`。支付 HTTP 必须使用测试替身，不能用真实商户做自动化付款/退款。
- 三类合作意向表单默认免费、私密，关闭后旧邀请入口也不能提交；不应意外接入收费或自动邮件。
- 倒计时采用服务器时间，目标为北京时间选定日期 00:00；旧会议默认关闭，不能替用户启用。

## 验证与交付

- 按改动范围验证，先阅读脚本再运行。部分早期 `verify_*` 会编辑既有演示记录或保留示例，不能盲目批量执行。
- 验收脚本放在 `tests/backend/`（Python）和 `tests/browser/`（Playwright/诊断），不要继续添加到根目录；从项目根运行命令。浏览器的 Docker 工作目录、私有文件和截图路径必须以项目根定位，不能误用测试目录。
- 本机配置测试：`D:/python/python.exe -m unittest discover -s tests/backend -p test_smtp_config.py`。前端局部单元测试保留在 `frontend/`。
- 后端支付/状态变更：`tests/backend/verify_review_regressions.py`、`tests/backend/verify_payments.py` 复制到容器运行；UI：`node tests/browser/verify_payments_ui.cjs`。命令见 README。
- 基本信息与首页：对应 `verify_feedback_*`；检索：`tests/backend/verify_conference_search.py`；倒计时：`tests/backend/verify_countdown.py` / `tests/browser/verify_countdown_ui.cjs`。优先选择能覆盖触发条件的检查。
- 前端：`npm run build`，`node --test frontend/apiErrors.test.mjs`（后者从项目根运行）。部署可用性：`D:/python/python.exe tests/backend/verify_service_recovery.py`，它不打印运行密钥。
- 报告说明本次实际运行结果，不把历史通过当成本轮通过；真实邮箱送达、原手机微信内核和真实商户支付仍需单独验收。
- 功能/启动/数据路径变化时同步 README 与相应 docs；协作规则变化时更新本文件。只改文档时检查路径、链接和敏感数据即可，不重启服务或执行会写库的业务测试。

## PDF 与本机文件操作

- 查看 PDF 使用 Poppler 转 PNG：`D:/DevTools/poppler/poppler-26.02.0/Library/bin/pdftoppm.exe -png -r 150 input.pdf out`。提取文字用同目录 `pdftotext.exe`；不另装 PDF 渲染器。
- 多页只看目标页时使用 `-f` / `-l`；Python 只能用 `D:/python/python.exe`，pdf2image 的 poppler_path 指向上述目录。
- Windows 文件删除/移动使用同一 PowerShell，先确认绝对目标路径在预期目录内；不要把枚举路径拼接到 cmd 或另一个 shell 执行递归删除。
