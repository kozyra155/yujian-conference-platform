# 预制外观验收（2026-10-15）

## 来源与实现范围

用户提供CASCONF外观管理截图，展示“简约1/简约2”各六种配色。实际浏览器访问 `https://yunjisuan221.casconf.cn/platform/config/exterior` 跳转 `/403`，提示没有权限；公开会议首页跳转 `/unpublished`。公开前端脚本可读取，但没有取得该账号的完整模板HTML/CSS或导出包。

因此当前实现是依据截图结构重新制作的遇见科技预制外观，不能称为从原后台导出了十二套原模板。没有引入第三方运行脚本、账号信息、机构照片或原站备案信息。缩略图为本项目SVG布局示意，真实预览使用本会议已保存内容。

## 使用

登录会议管理者或管理员，打开会议工作台 → 首页设计 → 预制外观。“发布概览”的“调整网站外观”和“站点设置”的“调整外观”也会进入该位置。

体验站61的选择入口：<http://localhost:12880/conference/61/?tab=design#appearance-presets>。本轮没有替换体验站61或会议22的外观；新增能力适用于所有平台托管会议。

- 简约1：大横幅、顶部横向导航、正文与右侧信息栏。
- 简约2：桌面左侧导航、右侧横幅与宽正文、正文下方信息网格，浅色页脚。
- 每套布局都有橙、红、紫、蓝、深蓝、绿六种配色，共十二种。
- 点击卡片只改变当前页面的待保存外观；点击“预览当前外观”打开桌面/手机预览，不保存会议数据。
- “保存首页设计”才应用到网站。仍可单独调整强调色，使用自定义颜色时不误选某个预设。
- 旧模板选择预设后会在本地切换为完整学术模板并提示；保存后补齐缺失栏目，已有内容保留。

预览只显示服务器已保存的会议文字和图片，未保存文字不出现在预览中；预览内链接已停用。预览与实际发布页面复用同一个SSR模板及CSS。

## 数据与权限

沿用`content.theme`，新增`layout`（simple-1/simple-2），旧数据默认simple-1且保留原accent。GET仅补充内存默认值，不写数据库。十二项catalog由`appearances.py`统一定义，随私有内容接口返回。

原内容保存接口继续使用CSRF、完整管理权限、会议锁定和修订号并发检查。布局枚举和六位hex颜色严格验证，拒绝额外字段/脚本/CSS注入。切换布局和配色不重建会议，不替换嘉宾、动态、图片或已有栏目。预览接口`POST /api/conferences/<id>/appearance-preview`返回私有no-store HTML，同样要求登录/管理权限/CSRF/未锁定。

原生`menu_entries_for_event`可能在单独事务中自动补齐菜单，所以预览在启用自定义菜单时直接读取已有MenuEntry；关闭自定义菜单时仍使用原生瞬态菜单。实际断言比较预览前后的全部插件设置、修订号、模板、菜单及页面内容，确认预览无会议数据写入。

## 验证记录

| 检查 | 结果与范围 |
| --- | --- |
| `tests/backend/verify_appearance_api.py`（容器） | 通过：12项catalog、所有预设实际保存、旧数据默认无写入、预览无写入/不切换旧模板、字段与注入拒绝、ACL/CSRF/锁定 |
| `tests/backend/verify_appearance_rendering.py`（容器） | 通过：12种主题实际SSR、旧模板强制预览、私有缓存、不修改源内容 |
| `node tests/browser/verify_appearance_public.cjs` | 通过：临时会议循环保存并公开显示12种外观、内容/9个导航保持、两种真实布局位置、320/390/760/1440无溢出，浏览器无pageerror |
| `node tests/browser/verify_appearance_editor.cjs` | 通过：12张卡片、选择不保存、实际预览不写入、保存重开、旧站升级内容保持、自定义色取消预设、Space/方向键、320/390px、预览链接禁用、403保留草稿 |
| `node tests/browser/verify_appearance_contrast.cjs` | 通过：真实Chromium解析CSS与像素颜色，2种布局×6种预设以及白/黄自定义色，信息栏标题和日期标签对比度≥4.5 |
| `tests/backend/verify_complete_site.py`（容器） | 通过：原有完整建站后端、修订号/并发、附件图片归档/权限、同名目录和跨会议/会话回归 |
| `tests/backend/verify_complete_rendering.py`（容器） | 通过：原导航ACL、显隐过滤、清洗、双语回退、报名投稿状态与旧模板路由 |
| `node tests/browser/verify_complete_public.cjs` | 通过：原完整站图片上传、发布/撤回、中英、下拉导航及响应式 |
| `node tests/browser/verify_complete_editor.cjs` | 通过：完整首页编辑的双语、增删排序显隐、上传移除、409/403、保存预览提示及320/390px回归 |

新增功能的失败测试已在实现前观察到：API缺少catalog，编辑器无12张外观卡片，渲染器不接受theme_override参数。预览初次测试发现原生菜单自动补齐，已修复为只读。独立复核发现原橙色小字对比度2.59，已改为深色文字、浅色底及强调色边框，回归通过，复核关闭。

桌面截图：`../output/appearance-simple-1-desktop.png`、`appearance-simple-2-desktop.png`；手机截图：同目录`appearance-simple-1-mobile.png`、`appearance-simple-2-mobile.png`。选择器截图：`appearance-picker-1440.png`、`appearance-picker-390.png`、`appearance-picker-320.png`。弹窗预览截图：`appearance-preview-simple-2-desktop.png`、`appearance-preview-simple-2-mobile.png`。实际布局、选择器及弹窗截图已人工检查。

真实浏览器以host-a只读打开体验站61工作台的直接外观URL，确认12卡片可见，并验证“发布概览→调整网站外观”正确切换到选择器。未保存或更改61的主题。

## 源码与部署

- `worker/extension/yujian_site/appearances.py`：共享预设与验证。
- `site_content.py`、`blueprint.py`：默认结构、catalog、只读预览接口。
- `display.py`、`templates/complete-conference.html`：外观参数、只读菜单与布局类。
- `portal/appearance-presets.css`：实际布局/配色/响应式。
- `frontend/src/AppearancePicker.vue`、`SiteContentEditor.vue`：选择器、SVG缩略图、预览与共用保存状态。
- `frontend/src/App.vue`：外观入口与直接打开首页设计的URL参数。

生产构建完成，Python服务已重启；没有添加依赖，浏览器不访问第三方主题CDN。构建沿用既有JS体积提示。

## 边界

当前十二种是两种布局×六种配色；不是十二种完全不同的页面结构。用户提供可访问的原模板导出包后，才可以进一步对照原HTML/CSS精确适配。显式启用原生自定义CSS/主题的旧会议仍走原生展示；如要用本预制外观，需要在原生外观中停用其自定义主题。已发布网站保存会立即应用，无独立历史版本或延后生效功能。
