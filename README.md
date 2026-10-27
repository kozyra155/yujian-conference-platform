# 遇见科技 · Indico 本地验证

这是基于官方容器配置的独立验证环境，固定 Indico 3.3.13。数据库、Redis 和附件均使用项目 `yujian-indico-v1` 的独立数据卷；HTTP 端口绑定本机和当前内网地址。

文档同步日期：2026-10-27。当前功能包括一键建站、十二种外观、14 个首页模块、中英文、会议筛选、邮箱注册、报名投稿、公司收款订单及会议倒计时。2026-10-27 重跑的 19 组后端容器检查全部通过；两组浏览器验收在页面导航阶段超时，未通过，详见 [本轮容器集成测试记录](docs/container-integration-20261027.md)。

开发约定见 [AGENTS.md](AGENTS.md)；最近修复见 [10 月 23 日审查修复记录](docs/review-fixes-20261023.md)。本仓库只包含定制源码、构建文件、测试和说明，不包含运行数据库、附件、账号密码或商户密钥。

## 内网访问

2026-10-15 已开放 TCP 12880，同一局域网访问 <http://192.168.2.36:12880/>。Windows 防火墙规则 `Yujian-Conference-LAN-12880` 仅放行本地子网到该内网地址/端口，适用于当前网络配置文件。数据库、Redis及应用内部端口仍无宿主机发布。

Indico 的 `BASE_URL` 已同步为内网地址，避免地址校验失败或生成localhost链接。原本的 <http://localhost:12880/> 和127.0.0.1入口会以307跳转至内网站点，登录会话使用内网地址，首次切换可能需要重新登录。

本机网页与实际登录/工作台已验证，另从应用容器请求Windows内网地址返回200；尚未从另一台实体电脑实测。可运行 `node tests/browser/verify_lan_access.cjs` 复查实际登录、资料表单和工作台，测试账号会清理。现有验证/预览脚本也已同步站点地址。

此地址取自当前网卡，IP变化后需同步 `docker-compose.yml` 的内网绑定、私有 `indico.conf` 的 `BASE_URL`、`nginx.conf` 的本地跳转及防火墙规则LocalAddress，并重启应用、重新创建Nginx。建议在路由器中为这台电脑保留该IP。未配置公网映射或HTTPS。

## 启停

在此目录打开 PowerShell：

```powershell
Set-Location D:/works/yujian-conference-design/indico-demo
# Docker 未启动时先启动 Docker Desktop，等待引擎就绪。
Start-Process 'C:/Program Files/Docker/Docker/Docker Desktop.exe' -WindowStyle Hidden
docker version
docker compose up -d --no-build
docker compose ps
```

停止网站但保留数据：

```powershell
docker compose stop
```

首次构建：`docker compose build indico-web`。启动后访问 <http://192.168.2.36:12880/>。

镜像重建并重新创建应用容器后，执行 `docker compose restart indico-nginx`，刷新代理使用的应用地址。访问时使用上述内网地址，并确保代理不拦截内网请求。

`stop` 保留数据。不要使用 `down -v`，它会删除本演示的数据库和附件数据卷。

只读检查六个服务、自动重启策略和主要页面：`D:/python/python.exe tests/backend/verify_service_recovery.py`。

## 新环境配置

本目录是应用项目根目录。克隆仓库后先从示例创建本地配置：

```powershell
Copy-Item .env.example .env
Copy-Item indico.conf.example indico.conf
Copy-Item smtp-settings.example.json smtp-settings.json
Copy-Item payment-config/merchant.example.json payment-config/merchant.json
```

填写独立数据库密码和随机 `SECRET_KEY`；核对 `BASE_URL`。当前 Compose、Nginx 和验证脚本使用 `192.168.2.36:12880`，换机器时须同步地址、端口和防火墙规则。SMTP 与在线支付示例均默认关闭。首次构建和初始化与已有环境启动不同：需构建镜像、初始化数据库及平台目录/管理员；下方种子脚本只用于全新演示环境，不能当作日常启动脚本。

需要演示种子账号时，从 `demo-accounts.example.json` 复制到本地 `demo-accounts.json`，为三个账号分别填写强密码后使用。克隆源码不会恢复现有会议、注册账号和上传文件。

## 数据存储与 Docker 迁移

- PostgreSQL 保存用户、会议、报名、投稿、订单和配置，位于 Compose 命名卷 `postgres-data`；上传文件位于 `archive` 卷，容器内路径 `/opt/indico/archive`。
- Redis 使用 `redis` 卷；生成的静态资源、日志分别使用 `static-files`、`indico-logs` 卷。实际卷名带 `yujian-indico-v1` 前缀。
- 2026-10-22 已将本机 Docker 运行数据迁至 `D:/DockerData`：主数据盘 `disk/docker_data.vhdx`，WSL 系统盘 `main/ext4.vhdx`。Docker Desktop 程序仍在 `C:/Program Files/Docker/Docker`。
- 兼容目录 `C:/Users/Admin/AppData/Local/Docker/wsl/disk` 是指向 D 盘的目录映射，不能按重复文件递归清理。
- 迁移备份保存在 `D:/DockerBackups/migration-20261022-091735/`，包含完整冷镜像、数据库和附件备份。这些是本机私有文件，未包含在仓库中。恢复前先停止服务并保留当前数据；不在 Docker 运行时直接搬动 VHDX。

## 初始化与验证

私有设置位于 `.env`、`indico.conf`；演示账户位于 `demo-accounts.json`。这些文件已列入 `.gitignore`，不要公开上传。

```powershell
docker compose cp demo-accounts.json indico-web:/tmp/demo-accounts.json
docker compose cp seed_demo.py indico-web:/tmp/seed_demo.py
docker compose cp tests/backend/verify_demo.py indico-web:/tmp/verify_demo.py
docker compose exec -T indico-web /opt/indico/.venv/bin/python /tmp/seed_demo.py
docker compose exec -T indico-web /opt/indico/.venv/bin/python /tmp/verify_demo.py | Set-Content -Encoding utf8 verification.json
node tests/browser/verify_browser.cjs
```

初始化可重复执行，复用已有账户、会议和自定义页面。浏览器验证使用本机现有的 Playwright 安装（`D:/playwright-demo/node_modules/playwright`），输出截图到上一级 `output` 目录。

## 范围

已完成本地一键建站流程及下文的报名、投稿、公司统一收款和倒计时。原有环境已配置 SMTP；实际邮箱收件仍需确认。尚未包含域名绑定、独立草稿内容版本或正式公网部署，微信/支付宝仍需真实商户与公网 HTTPS 联调。

本机曾发生 Docker / WSL 中断，已用 `worker/Dockerfile.local-repair` 为已有镜像补装字体渲染库、修正脚本换行及字体缓存权限。此文件依赖本机已有 `yujian-indico:3.3.13` 镜像，不能代替首次构建；完整配置已同步到 `worker/Dockerfile`。从零构建修正后的完整配置未再次验收，详见报告。

上游出处与改动见 [UPSTREAM.md](UPSTREAM.md)。最终通过项和实际入口见 [验证报告](docs/indico-validation.md)。

## 遇见科技门户首页

首页 http://localhost:12880/ 由 `portal/index.html`、`styles.css`、`app.js` 和本地品牌素材提供，布局参考 CASCONF。Nginx 接管 `/`、`/events/` 与 `/portal-assets/`；会议详情、登录、创建和管理由 Indico 与定制扩展处理。

前端文件以只读目录挂载，修改后刷新浏览器即可。首次添加挂载或修改 Compose 配置后执行 `docker compose up -d --no-deps indico-nginx`。Nginx 配置改动后先运行 `docker compose exec -T indico-nginx nginx -t`，通过后再 reload 或重新创建此容器。

创建入口为 `/conference/create/`。已完成原生验证的有效登录账号可自助创建；后台仅授予平台目录的 `create` 权限，不授予目录管理、全局管理员或其他会议管理权限。完整学术模板生成主导航和子页面，新网站作为私密草稿保存。

运行 `node tests/browser/verify_portal.cjs` 验证首页搜索、导航、轮播、公告、创建表单与响应式布局，运行 `node tests/browser/verify_browser.cjs` 复测原有会议和权限隔离。首页与活动页读取 `/api/conferences/`，发布和撤回自动反映到列表。旧宣讲会已移除；会议卡片支持时间、学科、城市、关键词筛选和显示时区/语言设置，见 [会议检索](docs/conference-search-plan.md) 与 [会议卡片](docs/conference-cards-validation.md)。

## 公司品牌素材

`portal/meet-logo.png` 与 `portal/meet-background.png` 是用户提供的原图副本，未修改图片内容。首页通过 `brand.css` 适配，登录页通过 `auth-brand.css` 和 `auth-brand.js` 适配。

`customization/templates/` 通过只读挂载使用 Indico 的模板扩展机制；登录页仍继承原有表单、CSRF、错误消息与登录事件。`indico.conf` 中 `LOGIN_LOGO_URL`、`LOGO_URL`、`FAVICON_URL` 均指向 `/portal-assets/meet-logo.png`。增加模板挂载后执行 `docker compose up -d --no-deps --no-build indico-web`，随后 `docker compose restart indico-nginx`；后续模板或应用配置修改后需要重新启动应用以清除缓存。

运行 `node tests/browser/verify_brand.cjs` 验证素材、登录、CSRF 字段、会议权限和手机布局。截图位于 `../output/yujian-brand-desktop.png`、`yujian-brand-mobile.png`、`yujian-login-desktop.png`、`yujian-login-mobile.png`。

## 会议活动与注册页

会议列表：<http://localhost:12880/events/>；注册：<http://localhost:12880/register/>。

运行 `D:/python/python.exe build_events.py` 组装会议列表页。运行 `node tests/browser/verify_events.cjs` 检查筛选、搜索、时区、会议状态和手机布局。

注册页面复用原有验证码和表单。验证第二步需先生成一个内部 UI 测试链接：

```powershell
docker compose cp make_register_preview.py indico-web:/tmp/make_register_preview.py
docker compose exec -T indico-web /opt/indico/.venv/bin/python /tmp/make_register_preview.py
docker compose cp indico-web:/tmp/register-preview.json .register-preview.json
node tests/browser/verify_register.cjs
```

测试链接有效期一小时，不要公开；测试不发送邮件或创建账号。会话结束后可删除该临时 JSON。

## 企业 SMTP

私有配置为 `smtp-settings.json`，默认关闭真实发信。填写完整企业邮箱账号和客户端授权码后，运行 `D:/python/python.exe check_smtp.py` 检查认证；它不会发送邮件。认证成功后设置 `enabled: true` 并执行 `docker compose restart indico-web indico-celery indico-celery-beat` 使配置生效。首次新增挂载需运行 `docker compose up -d --no-build`，并重启 `indico-nginx`。

`D:/python/python.exe check_smtp.py --connect-only` 仅检查加密连接；`D:/python/python.exe -m unittest discover -s tests/backend -p test_smtp_config.py` 检查配置校验。`tests/backend/verify_demo.py` 现在兼容演示与真实 SMTP 模式，但仅做模型、权限和设置检查，不发送邮件。`tests/backend/verify_smtp_runtime.py` 可在应用及 Celery 容器内检查真实配置及认证，也不发送邮件。

2026-10-14 已按用户提供的 QQ 邮箱账号修正为 `smtp.qq.com:465` 并启用 SSL。配置通过 `locals().update(...)` 加载，以适配 Indico 配置解析器；原先 `globals().update(...)` 不会覆盖设置。应用及后台任务的认证已验证，实际邮件收件仍需单独确认。

部署、截图、验证范围与尚未完成的邮件送达见 [本轮记录](docs/events-and-registration.md)。

## 登录状态与中英文

门户顶栏读取真实会话，登录后显示账户菜单；右上角 `EN / 中文` 支持首页、会议活动、登录和注册页，语言选择跨页面保持，并同步原生界面偏好。账户信息不存入浏览器本地存储。

会话模板通过既有用户变量视图提供精简响应，Nginx 禁止缓存。修改共享门户页头或翻译脚本后运行 `D:/python/python.exe build_events.py`；修改模板后重启 `indico-web` 清除模板缓存。修改 Nginx 配置需先 `nginx -t` 再 reload。

运行 `node tests/browser/verify_session_language.cjs` 验证会话、语言和手机布局；该测试使用现有演示账户，不发送邮件。详细边界与截图见 [门户会话与语言记录](docs/portal-session-language.md)。

## 一键建站

- 创建网站：<http://localhost:12880/conference/create/>
- 我的网站：<http://localhost:12880/organizer/>
- 验收示例：<http://localhost:12880/event/4/>，标明为体验会议，不接受真实报名。

填写标题、时间（中国标准时间）、地点和简介，默认使用完整学术模板，也可选择学术蓝或科技绿模板。工作台可维护基本信息、首页设计和原生栏目。发布后任何人都能访问，且会议自动进入公开列表；撤回恢复私密，已有内容保留。

草稿只允许会议管理者和管理员访问。当前使用同一份内容：已经发布的网站保存编辑会即时影响公开页面；如需先预览修改再公开，应先撤回。尚未实现独立内容版本。

草稿检查同时覆盖原生页面、事件及附件权限，以及旧版文件导出。为使撤回立即生效，扩展关闭原生旧版 HTTP API 的结果缓存；导出会重新计算。原生会议锁定也会阻止发布或撤回操作。

扩展源码与发行元数据位于 `worker/extension/`，通过只读挂载和 `PYTHONPATH` 使用标准插件入口 `yujian_site`，无需修改上游源码或安装新依赖。私有 `indico.conf` 中须配置 `PLUGINS = {'yujian_site'}`。首次增加扩展挂载后执行 `docker compose up -d --no-build` 并重启 Nginx；Python 改动需重启 Web、Celery 和 Beat。

修改门户头尾后同时运行 `D:/python/python.exe build_events.py` 和 `D:/python/python.exe build_builder.py`。工作台内容来自 `frontend/src/App.vue`；`builder.html` 为生成的品牌外壳，不能直接修改。

老演示环境接入工作台时，可执行以下幂等迁移，仅补充缺失地点及网站管理状态，不重置栏目或配色：

```powershell
docker compose cp backfill_demo_locations.py indico-web:/tmp/backfill_demo_locations.py
docker compose exec -T indico-web /opt/indico/.venv/bin/python /tmp/backfill_demo_locations.py
```

验收命令：

```powershell
docker compose cp tests/backend/verify_site_builder.py indico-web:/tmp/verify_site_builder.py
docker compose exec -T indico-web /opt/indico/.venv/bin/python /tmp/verify_site_builder.py
node tests/browser/verify_builder_browser.cjs
D:/python/python.exe -m unittest discover -s tests/backend -p test_smtp_config.py
```

后端测试使用测试签名链接走原生注册接口，在测试进程内禁用外发邮件，并将临时账号及会议标记删除；不会修改真实账号。浏览器测试使用现有 host-a，复用或创建唯一的体验会议并保留为公开验收示例，测试中会编辑其委员会栏目及切换发布状态。

详细结果、入口及边界见 [一键建站验收记录](docs/site-builder-validation.md)。

## 统一工作台与会议展示站

2026-10-14：会议目录 `/category/1/`、创建 `/conference/create/`、个人工作台 `/user/dashboard/` 与 `/organizer/`、网站管理 `/conference/<id>/` 统一使用 Vue 3 + Element Plus。组件构建后存入 `portal/ui-dist/`，浏览器不请求外部 CDN。目录和个人会议均接真实接口；个人会议按原生完整管理权限显示，包含授权的协作管理者和管理员。当前列表在服务端扫描平台网站后判断权限，大规模部署需增加 ACL 查询优化和分页。

公开会议首页和自定义栏目通过插件在原生权限检查后渲染，参照 EAAMS 使用学术横幅、横向导航、正文与右侧重要日期。只展示可见菜单及其内容，保留自定义首页、强制概览、主题预览、HTML 清洗及私密草稿规则。会议标志、横幅方式、背景配色和公告继续读取原生设置；主动选择原生主题或自定义 CSS 时继续使用原生渲染与预览；额外插件的展示钩子未迁移到新版展示模板。原生编辑器、个人资料和参会记录使用统一样式及移动端导航，保留业务表单；原生日程参会记录入口为 `/user/dashboard/?legacy=1`。

前端修改后的构建：

```powershell
Set-Location frontend
npm ci
npm run build
Set-Location ..
D:/python/python.exe build_builder.py
docker compose -p yujian-indico-v1 restart indico-web indico-celery indico-celery-beat
```

测试：`node tests/browser/verify_workspace_ui.cjs`（目录、工作台、中英、搜索乱序与响应式）、`node tests/browser/verify_workspace_creation.cjs`（真实组件表单创建并清理临时会议）、`node tests/browser/verify_native_ui.cjs`（编辑器、资料、参会记录及手机布局）。既有 `tests/backend/verify_site_builder.py`、`tests/browser/verify_builder_browser.cjs`、`tests/browser/verify_portal.cjs`、`tests/browser/verify_session_language.cjs` 保留并继续验证。详细记录见 [界面验收](docs/workspace-ui-validation.md)。

2026-10-15：进一步重做栏目编辑与个人中心。托管会议的原生栏目编辑地址保持不变，由插件在原生授权后渲染新工作台，Element Plus 工具栏配合原生富文本、菜单及排序逻辑。自定义菜单关闭时可以直接启用，锁定会议只读。当前用户资料及参会记录通过 `customization/templates/core/users/` 扩展原生模板，保留 React 表单、账号功能、角色数据与日历入口。源码及验收细节见 [栏目编辑与个人中心验收](docs/menu-editor-validation.md)。

运行 `node tests/browser/verify_menu_editor.cjs` 只读检查会议 22；运行 `node tests/browser/verify_user_frame.cjs` 检查资料/记录和语言输入保持；运行 `node tests/browser/verify_menu_editor_flow.cjs` 使用临时账号及会议验证真实保存、添加、编辑、显隐、首页、拖拽、删除、菜单重新启用及锁定权限，最后将临时数据标记删除。

## 完整学术会议模板

2026-10-15：创建会议默认选择“完整学术会议”，自动生成九个主导航及会议组织子页面。网站工作台增加“首页设计”：编辑横幅、嘉宾照片、会议动态、重要日期、单位分组及Logo、联系信息、参会须知、酒店与报名投稿入口，支持增删、排序、显隐和首页中英文内容。旧会议在该标签主动选择完整模板并保存后升级，已有栏目与内容保留。

公开完整体验站：<http://localhost:12880/event/61/>；管理页：<http://localhost:12880/conference/61/>（管理者登录）。这是明确标注的示例，不接受实际报名或缴费，未修改会议22。

原生报名/摘要投稿已经接到实际业务，主办方仍需配置表单、开放时间等；也可选择外部链接。收款与开票状态以后文“公司统一收款”为准。图片用原生附件归档与会议权限，Nginx允许6MiB请求，应用图片上限5MiB。完整验收、使用方式、源码和边界见[完整会议建站验收](docs/complete-conference-validation.md)。

新增检查：`node tests/browser/verify_complete_editor.cjs`、`node tests/browser/verify_complete_public.cjs`、`node tests/browser/verify_complete_mobile.cjs`，以及容器内运行`tests/backend/verify_complete_site.py`、`tests/backend/verify_complete_rendering.py`、`tests/backend/verify_complete_business.py`。这些测试使用临时记录且不发送外部邮件。

## 十二种预制外观

2026-10-15：网站工作台 → 首页设计 → 预制外观，新增简约1（横向导航）和简约2（桌面左侧导航）各六种配色，共十二种。选择后可以预览实际会议内容，保存才应用；保留已有文字、图片、导航和业务数据。预览支持桌面/手机且不会写入会议设置或栏目。旧外观与自定义强调色仍可使用。

入口示例：<http://localhost:12880/conference/61/?tab=design#appearance-presets>。本轮未修改会议22或61的主题。参考后台返回403，未获取原模板导出文件；这些外观为按用户截图重新实现的本地主题，非原站模板源码导入。[实现边界和验收记录](docs/appearance-presets-validation.md)。

## 报名、投稿评审与参会中心

2026-10-15：网站工作台新增“报名与投稿管理”，地址为 `/conference/<id>/operations/`，汇总实际报名人数、待审核人数、稿件及状态，并连接原生表单配置、名单审核/导出、征稿和审稿管理。个人入口 <http://localhost:12880/participation/> 汇总本账号报名、稿件和未完成审稿任务，支持搜索、状态筛选和中英文切换。原生报名、字段编辑、稿件及评审页面使用统一工作台外壳，保留原生业务和权限。

真实报名审批/CSV、投稿评审/录用及状态同步已使用临时数据和内存邮件验证。接口不返回他人邮箱或报名令牌；审核后未审数量即时扣除，草稿/撤回/锁定规则保留。支付和开票已在后续版本补齐，详见下节。[报名投稿使用方法与验证](docs/conference-business-validation.md)。

## 会议访客注册与邮箱验证

2026-10-15：会议网站的注册/登录与报名/投稿入口现在保留会议上下文，邮箱验证后创建原生账号、自动登录并返回原会议业务页面。支持邮件链接在新浏览器打开，保留原生图片验证码、CSRF、限流、密码及邮箱规则；同一账号可参加多个会议。手机端也显示注册入口，登录后隐藏。

当前仍使用邮箱验证链接；未增加数字邮箱验证码或机构SSO。会议入口为 `/event/<id>/register/` 和 `/event/<id>/login/`，通用注册入口为 <http://192.168.2.36:12880/register/>。会议需先发布并配置开放的报名表，账号注册本身不会自动开放会议。

真实验证/注册/报名/投稿在内存邮件后端测通，Web与Celery的SMTP连接认证成功，实际邮箱收件仍待确认。[使用方法、验证与现有会议状态](docs/conference-account-validation.md)。
## 公司统一收款

已新增公司收款配置、人民币收费订单、对公转账待核对、管理员确认到账、全额退款登记、发票申请/登记及财务CSV。入口：[公司收款配置](http://192.168.2.36:12880/company/payments/)（管理员）；每场会议“办会管理 → 收费与订单”，参会者“我的参会 → 去付款”。

是否允许收费取决于管理员启用并填写完整公司账户；微信/支付宝接入代码已具备，但公司商户资料和公网HTTPS未配置时保持关闭。退款由财务实际退回后登记，发票由财务实际开具后登记。[配置、流程、验证与限制](docs/conference-payments-validation.md)。

2026-10-23 已修复已有订单的原生报名撤销/重置/改价风险、过期支付信息恢复和会议时间精度。过期支付先查单，再根据渠道结果关单或登记到账；异常到账保留为“到账待核对”，可走财务全额退款流程，不会自动批准异常报名或开票。已有财务订单的原生修改被拦截，不能直接绕过财务流程。详见 [修复与验证](docs/review-fixes-20261023.md)。

## 会议横幅参会入口

会议首页及栏目页横幅下方新增“报名参会 / 登录”，登录后显示“我的参会”。完整横向、侧栏及旧版模板均支持，复用邮箱验证注册、真实报名及既有付款业务。报名未开放或入口被主办方关闭时显示禁用状态。[使用与验证](docs/conference-entry-validation.md)。

## 1016 反馈与倒计时

已补充 45 个学科、17 个计划检索选项、地区与主办方信息、14 个首页模块、嘉宾角色与简介、委员会成员、批量图片和联系表格；三类合作意向复用免费私密表单。完整学术模板的“首页设计 → 会议倒计时”可设置目标日期，按北京时间目标日 00:00 显示天/时/分/秒；留空跟随会议开始日期，旧会议默认关闭。

[反馈验证与剩余项](docs/feedback-1016-validation.md)、[倒计时说明](docs/countdown-validation.md)。尚未完成任意自定义模块、自由拖动横幅文字、委员会树状图等扩展；原手机微信环境的邮箱重复验证现象仍需新邮件实机确认。

## 最近修复的验证命令

2026-10-27 已将验收脚本统一归入 `tests/backend/` 与 `tests/browser/`；按功能选择命令见 [测试说明](tests/README.md)。根目录不再保留 `verify_*` 或浏览器诊断脚本。

以下后端测试在容器中运行；支付测试只创建独立临时数据并使用内存邮件、模拟支付网络。先阅读测试脚本；早期演示验证可能操作既有示例账号和会议，不能直接批量运行全部 `verify_*`。

```powershell
docker compose cp tests/backend/verify_review_regressions.py indico-web:/tmp/verify_review_regressions.py
docker compose exec -T indico-web /opt/indico/.venv/bin/python /tmp/verify_review_regressions.py
docker compose cp tests/backend/verify_payments.py indico-web:/tmp/verify_payments.py
docker compose exec -T indico-web /opt/indico/.venv/bin/python /tmp/verify_payments.py
node tests/browser/verify_payments_ui.cjs
node --test frontend/apiErrors.test.mjs
D:/python/python.exe tests/backend/verify_service_recovery.py
```

2026-10-23 上述检查通过；新增回归为 10 项，付款界面覆盖 320/390/1440 像素。未发生真实支付、退款或外发邮件，未修改会议 22、61、171。
