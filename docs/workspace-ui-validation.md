# 遇见科技工作台界面验收

日期：2026-10-14，地址：`http://localhost:12880/`。

## 本轮范围

| 页面 | 实现 |
|---|---|
| `/category/1/` | 公开会议目录、名称/地点查询、会议卡片、分页、加载/空结果/错误状态 |
| `/category/1/#create-event:conference:1` | 进入新版创建表单，未登录时先登录 |
| `/conference/create/` | Element Plus 表单、日期时间选择、模板选择、校验、提交反馈 |
| `/user/dashboard/`、`/organizer/` | 我的会议、实际统计、筛选、管理与预览、手机端参会记录入口 |
| `/conference/<id>/` | 发布概览、栏目指引、站点设置、发布/撤回确认、网址复制 |
| `/event/<id>/` 和会议栏目 | 学术横幅、横向栏目、正文、日期/快捷入口侧栏、联系入口 |
| 原生栏目编辑、个人资料、参会记录 | 统一品牌样式、返回工作台、手机导航；业务表单沿用原生实现 |

Vue 3.5.44、Element Plus 2.14.7、Vite 8.3.4 固定版本，依赖锁定在 `frontend/package-lock.json`，运行资源从本站提供。公司原始 Logo 沿用。会议内容与实际日期均沿用数据库，不用其他组织的人员、照片或联系信息填充。

## 已运行验证

- `npm run build`：本地生产构建成功。单个 JS 约 570KB、CSS 约 386KB（未压缩传输大小），构建工具给出较大 chunk 提示，未作为错误。
- `tests/browser/verify_workspace_ui.cjs`：指定原生入口、Element Plus 组件、目录搜索响应乱序保护、手机参会记录入口、界面中英文、会议标题保留，320/390/760/1440px 无页面横向溢出；320px 日期选择弹层检查通过。
- `tests/browser/verify_workspace_creation.cjs`：普通演示账号从原生 hash 入口进入创建页，日期组件解析正确，真实提交返回 201，生成私密草稿；匿名访问被拒绝，临时会议已标记删除。
- `tests/browser/verify_builder_browser.cjs`：体验会议 4 的原生富文本保存、草稿保护、发布、实际门户列表查询、撤回、再次发布、中英与移动端通过；最终保留体验会议公开。
- `tests/backend/verify_site_builder.py`：原生注册、创建、跨账号与 CSRF、锁定、附件、旧导出、草稿与只读 ACL 回归通过；新增协作管理者列表、权限撤回、受保护通知不出现在摘要、原生自定义首页、HTML 清洗和显式自定义 CSS 保留检查通过。使用进程内邮件后端，不外发注册邮件，临时账号及会议标记删除。
- `tests/browser/verify_native_ui.cjs`：原生编辑器、资料和参会记录的样式及 320/390/760/1440px 布局通过；手机导航展开和收起可用。
- `tests/browser/verify_portal.cjs`、`tests/browser/verify_session_language.cjs`：首页搜索、导航、创建入口、实际登录状态、语言保持和退出登录通过。

截图位于项目上级 `output/`：`yujian-directory-desktop.png`、`yujian-dashboard-desktop.png`、`yujian-builder-create-desktop.png`、`yujian-workspace-mobile.png`、`yujian-site-desktop.png`、`yujian-native-editor-mobile.png`。

独立代码审查指出目录请求乱序及手机参会入口缺失，均已修正并加入浏览器验证。会议栏目显示逐级检查原生可见性，不从受保护栏目提取公开摘要。

## 边界

仅本地验收，未发布公网。主办方填写的正文不自动翻译；界面支持中英文。复杂会务表单仍为原生 Indico，已统一样式。主动选择原生主题或自定义 CSS 时沿用原生渲染与预览；第三方展示钩子未迁移到新版模板；原生高级模块可继续从管理区访问。已发布站点仍使用同一份内容，编辑即影响公开页面；需要先预览修改时应先撤回。注册邮件实际收件验证不属于本轮 UI 验收。
