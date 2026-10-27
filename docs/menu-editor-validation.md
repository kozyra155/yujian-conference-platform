# 栏目编辑与个人中心验收

日期：2026-10-15。本地地址 `http://localhost:12880/`。

## 界面

- `/event/22/manage/layout/menu/`：全新工作台外壳、会议信息及发布状态、预览入口、Element Plus 搜索和分类、添加栏目菜单、带文字的行操作、显示状态与首页标记、编辑指南、高级设置。
- 默认显示内容页面和自定义链接，会务功能及全部栏目可单独查看。筛选只改变显示，不修改配置。只有全部栏目且搜索为空时启用拖拽，保证排序位置明确。
- 富文本继续使用原生 TinyMCE 和表单，图片上传、嵌套、可见性、ACL、首页、删除确认与 CSRF 逻辑均保留。关闭自定义菜单时有明确的启用入口；锁定时隐藏修改操作。
- `/user/profile/`：共享工作台、紧凑账号设置标签、更多设置菜单、重新排版的原生 React 资料表单。
- `/user/dashboard/?legacy=1`：共享工作台、资料摘要、关联会议和角色、关注目录与日历入口。
- 个人页面仅替换当前用户外壳，管理员查看其他用户时保留原生视图。语言偏好同步后，个人页面仅在没有用户输入或对话框时刷新原生标签；已有输入不会丢失。

## 实际验证

| 检查 | 结果 |
|---|---|
| `npm run build` | 成功，组件本地打包，无新增依赖 |
| `tests/browser/verify_menu_editor.cjs` | 会议 22 只读查看，新版工具栏；320/390/760/1440px 无横向溢出 |
| `tests/browser/verify_user_frame.cjs` | 资料与参会记录新外壳；同四种宽度通过；输入后切换英文保持原值 |
| `tests/browser/verify_native_ui.cjs` | 三类页面统一外壳、手机个人中心入口及布局通过 |
| `tests/browser/verify_menu_editor_flow.cjs` | 临时普通账号实际保存资料（原生 PATCH 返回 204），创建临时会议，搜索/分类、新页面、富文本读回和标题修改、显示切换、默认首页、鼠标拖拽与刷新后顺序、删除后列表刷新均通过 |
| 同上 | 390px 富文本对话框无横向溢出，中英、关闭菜单后的重新启用、锁定只读、匿名及跨账号拒绝通过；无浏览器 JS 错误 |
| `tests/browser/verify_builder_browser.cjs` | 已有建站、编辑、发布/撤回及门户列表闭环回归通过，体验会议 4 最终保持发布 |
| `tests/browser/verify_session_language.cjs` | 会话、语言保持、退出及原生兼容回归通过 |
| `tests/backend/verify_site_builder.py` | 注册、创建、草稿及附件/导出保护、页面 ACL、委托管理、HTML 清洗等后端回归通过 |

会议 22 未进行写入测试。临时账号和它创建的会议在 finally 中校验身份后标记删除。两项独立只读审查未发现实质权限或排序兼容性问题。

## 文件

- 插件模板及视图：`worker/extension/yujian_site/display.py`、`templates/menu-editor.html`、`templates/workspace-frame.html`。
- 当前用户页面扩展：`customization/templates/core/users/base.html`、`dashboard.html`。
- 组件与本地构建：`frontend/src/MenuToolbar.vue`、`main.js`、`portal/ui-dist/`。
- 样式与原生交互桥接：`portal/native-frame.css/js`、`portal/menu-editor.css/js`。
- 共享语言同步事件：`portal/portal.js` 新增 `meet-language-synced`，避免原生个人页在服务器偏好更新前刷新。

截图在上级 `output/`：`yujian-editor-22-desktop.png`、`yujian-editor-22-mobile.png`、`yujian-profile-new-desktop.png`、`yujian-profile-new-mobile.png`、`yujian-records-new-desktop.png`、`yujian-records-new-mobile.png`、`yujian-menu-rich-editor-desktop.png`、`yujian-menu-rich-editor-mobile.png`。

仅本地验收，未部署公网。资料表单和会务数据处理仍使用原生后台。本轮未验证外部日历软件实际订阅或编辑器图片上传；其原有组件和接口保留。
