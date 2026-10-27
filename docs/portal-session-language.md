# 门户会话与中英文切换

日期：2026-10-14。

## 行为

首页和会议活动页现在读取真实 Indico 会话。匿名显示登录入口；登录后显示账户名称和菜单，包含“我的会议”“个人资料”“退出登录”。退出沿用原生路由，不改变认证或会议权限。返回缓存页面、窗口重新获得焦点或标签页重新可见时，会再次检查会话。

右上角 `EN / 中文` 切换首页、会议活动、登录及注册页的自有界面文案。语言选择保存在浏览器，会议活动的语言下拉框与顶栏共用这一设置。通过已有 `/change-language` 接口和 CSRF 同步原生界面语言；登录和注册等原生表单在语言改变后刷新，以加载上游对应翻译。自行填写的姓名、会议信息等内容不会自动翻译。

后续修复：已填写或编辑过的表单切换语言时保留输入，仅更新本地文案，不直接刷新；未填写的表单仍可刷新加载原生翻译。账户菜单的“我的会议”现进入 `/organizer/` 网站工作台。

## 实现与隐私

`customization/templates/core/assets/vars_user.js` 为 `/assets/js-vars/user.js?portal=1` 提供门户用 JSON，只有当前用户 ID、名称、CSRF 和语言，不返回邮箱或其他个人资料。未携带 `portal=1` 时，保留原有 `Indico.User` JavaScript 输出。Nginx 将此视图响应标记为 `private, no-store`。

`portal/portal.js` 负责会话与界面翻译；身份只在内存中使用，不存入 localStorage。账户名称用文本节点显示。会话请求失败时清空旧账户并显示“账户”入口，不把旧身份当成有效登录。

`portal/translations.js` 保存自有文案；`app.js` 同时提供中英横幅，`events.js` 保留原有中文、英文会议资料。翻译通过文本节点和指定属性更新，保留表单、图标与事件，不通过 HTML 字符串解析用户名称。`portal/portal.css` 负责账户菜单、语言按钮和英文手机布局。

## 验证

- `tests/browser/verify_session_language.cjs`：真实登录后账户名称、匿名隔离、退出、精简会话、不缓存、后台脚本兼容、账户链接、语言持久化、后台语言同步、登录与注册文案、会话服务异常回退；英文 320、390、760、1024、1440px 无横向溢出。
- `tests/browser/verify_portal.cjs`、`tests/browser/verify_events.cjs`：首页原有查询、创建入口及会议列表筛选、时区、加载失败提示等行为通过。
- `tests/browser/verify_brand.cjs`、`tests/browser/verify_register.cjs`：品牌素材、真实登录和会议权限、CSRF、验证码保留及注册两步表单通过。

截图：英文登录状态首页（本机历史验收文件，未上传：`../output/yujian-home-signed-in-en.png`）。本轮不发送邮件，不创建真实账户；尚未进行其他浏览器内核或自动无障碍审计。
