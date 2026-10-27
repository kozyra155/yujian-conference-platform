# 会议活动与注册页优化

日期：2026-10-14。

## 会议列表

入口：<http://localhost:12880/events/>。首页导航“会议查询”和“查看全部会议活动”连接到新列表。

参照用户提供的本地 `1000help-website-dist/events.html`，使用三列卡片、地区筛选、关键词搜索、时区选择和中英文会议内容；延续现有遇见科技 Logo、旋涡背景及蓝绿色调。手机端改为单列。

导入资料中的 15 场线上宣讲会，保留原始 2026 年 8 月日期、会议名称、地区、主题和 Zoom 报名链接，不把过期场次改成未来日期。当前标为“已结束”，按钮为“查看原报名页”；没有访问或验证第三方报名页是否仍可报名，没有填写未提供的回放链接。两场真实 Indico 演示会议另列于下方。

`portal/events-data.json` 为静态导入资料；修改资料后刷新即可。它尚未对接 Indico 已发布会议 API。`events-content.html` 保存页面内容；页头、页脚复用首页，修改后运行 `D:/python/python.exe build_events.py` 生成 `portal/events.html`。共享 `navigation.js` 负责移动导航。

浏览器验证覆盖地区、产业筛选、关键词、无结果、上海与纽约时差、中英文内容、结束状态和加载失败提示；在 320、390、760、1024、1440px 宽度检查无横向溢出。

截图：桌面（本机历史验收文件，未上传：`../output/yujian-events-desktop.png`）、手机（本机历史验收文件，未上传：`../output/yujian-events-mobile.png`）。

## 注册页面

入口：<http://localhost:12880/register/>。邮箱验证与账户信息两步共享品牌框架，保留原有服务端表单、CSRF、验证码和 React 注册组件。

第一步提供中文文案、常用邮箱输入、验证码语音及刷新按钮、明显的发送按钮和登录链接；第二步继续使用原有姓名、单位、用户名和密码等字段，注册按钮显示“完成注册”。不改变校验或自动创建账户。

`tests/browser/verify_register.cjs` 检查无效邮箱拒绝、无 CSRF 提交 400、验证码字段保留、两步布局和密码不一致反馈。第二步用内部签名测试链接进入，仅用于 UI 验证；测试未发送邮件、未创建账户，不能视为真实邮件注册已验收。生成测试链接运行 `make_register_preview.py` 于应用容器，结果保存为已忽略的 `.register-preview.json`，有效期一小时。

截图：邮箱验证桌面（本机历史验收文件，未上传：`../output/yujian-register-desktop.png`）、邮箱验证手机（本机历史验收文件，未上传：`../output/yujian-register-mobile.png`）、账户信息桌面（本机历史验收文件，未上传：`../output/yujian-register-profile-desktop.png`）、账户信息手机（本机历史验收文件，未上传：`../output/yujian-register-profile-mobile.png`）。

## 企业邮箱待接通

已查询 `1000help.com` 的 MX 记录，指向 `mxbiz1.qq.com`、`mxbiz2.qq.com`，据此按腾讯企业邮箱预置 SMTP 连接。`smtp.exmail.qq.com:465` 已通过 TLS 连接检查，未认证、未发送邮件。

私有配置：`indico-demo/smtp-settings.json`，已加入忽略列表并以只读方式挂载到应用和后台任务。默认 `enabled: false`，发件账号与授权码为空，因此当前仍使用本地演示邮件后端。注册页明确提示不会收到真实邮件，不把测试后端当成邮件送达。

填写 `username` 为完整企业邮箱地址，`password` 为客户端授权码，先保留 `enabled: false`。运行 `D:/python/python.exe check_smtp.py` 仅检查认证，不发送邮件。认证成功后再将 `enabled` 设为 `true`，重新启动应用及后台任务，使实际发信使用 SMTP。`smtp_config.py` 校验必填信息和 TLS 配置，强制系统发信使用认证账户，保留队列处理；单元检查见 `tests/backend/test_smtp_config.py`。

当前缺少发件账号和客户端授权码，尚未验证真实邮件发送、收件箱送达或完整注册。仅配置 SMTP 不会使本地地址成为公网地址，外部参会者仍无法通过邮件访问 `localhost` 验证链接；面向外部使用前需配置正式可访问的域名。

### 2026-10-14 配置检查更新

用户已填写 SMTP 账号与授权码。填写的账号属于 `@qq.com`，与原预置企业服务器不匹配；已改成 `smtp.qq.com:465`、SSL 加密，主机和容器内认证均通过。用户授权码未输出到日志或报告。

修正了本地配置加载的命名空间问题：Indico 使用独立的 locals 字典解析配置，原先更新 globals 未覆盖演示后端，现改为更新配置 locals。真实 SMTP 已启用，应用和 Celery 已重新启动；`tests/backend/verify_smtp_runtime.py` 分别确认后台配置、认证、发件人约束和队列设置。注册页已移除“暂未开通邮件”提示，注册校验和页面检查重新通过。

尚未发送测试邮件，未确认收件箱送达；等待用户指定测试收件邮箱。后续注册请求会使用真实 SMTP 发信，不再处于禁止外发模式。仍仅绑定本机地址。
