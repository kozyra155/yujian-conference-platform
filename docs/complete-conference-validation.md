# 完整会议建站验收（2026-10-15）

## 结果与入口

完整学术会议模板已经接入现有一键建站。布局参照 UAVRS2026 的横幅、横向导航、双栏正文、嘉宾、会议动态、重要日期与单位侧栏，使用遇见科技品牌及项目自己的科学背景；未复制或热链参考站照片。

- 创建：<http://localhost:12880/conference/create/>，默认“完整学术会议”。
- 公开体验站：<http://localhost:12880/event/61/>。
- 体验站工作台：<http://localhost:12880/conference/61/> → 首页设计（会议管理者或管理员登录）。
- 已有会议：从我的会议进入工作台 → 首页设计 → 使用完整学术模板 → 保存。保留已有栏目内容、排序、显隐和权限，仅补充缺少的页面。会议22未切换或修改。

新完整会议生成九个主导航：会议首页、会议组织、会议日程、注册缴费、会议投稿、会议酒店、考察活动、历届会议、联系我们。会议组织包含组委会、专题召集人子页面。旧学术蓝/科技绿模板和原有六页初始化继续可用。

## 可维护内容

“首页设计”可以维护中文/英文横幅及文字、栏目强调色、正文模块顺序/显隐、嘉宾及照片、带日期的会议动态、重要日期或日期范围、单位分组及Logo、联系信息、参会须知、酒店地点说明及实际报名投稿入口。列表支持增加、删除、上移、下移和隐藏；英文留空回退中文。中文简介与内页继续通过原生信息/栏目编辑器维护，内页未增加独立英文版本。

图片真实上传到原生附件归档，限定PNG/JPEG/WebP、5MiB、2000万像素，校验实际内容。中文或英文横幅任意一张单独上传均能显示，另一语言回退到已有图片，已补充渲染回归断言。网站图片文件夹隐藏、继承会议权限，且直接归属本会议；已有同名普通或受保护文件夹保持不变。跨会议和会话附件不能作为网站图片引用。Nginx上限调整6MiB容纳multipart，实际约1.47MiB PNG HTTP上传已验证。

保存使用原生登录、CSRF、完整管理权限与锁定检查；修订号配合数据库会议行锁防止多人覆盖，两个同版本并发保存结果为200/409。409或403保留当前草稿；重新载入需确认；离开有未保存内容或正在上传时有浏览器提示。预览明确展示最近保存版本。

## 报名与投稿

完整模板启用原生registration/abstracts模块，入口默认关闭，主办方可选择平台功能或外部链接。编辑器提供原生配置链接。原生报名表未建好、未开放或满员时不展示可报名按钮；摘要投稿保留开放状态提示。外部投稿支持mailto。

真实集成验收创建临时报名表、开放临时摘要投稿，普通参会者经原生HTTP接口提交后，Registration与Abstract记录确实写入数据库，主办方能访问管理列表；撤回网站后参会者访问也被拒绝。测试邮件使用进程内locmem，不外发；原生邮箱校验使用标准测试域模式，未测试真实DNS/投递。

本轮没有接入支付网关、自动支付对账或自动开票。体验站61明确标为示例，所有嘉宾与单位资料均标注演示，不接受真实报名、投稿或缴费。

## 实际验证

全部以下命令在本轮运行并成功退出：

| 验证 | 覆盖 |
| --- | --- |
| `npm run build`（frontend） | Vue/Element Plus生产构建，最终JS约624kB；已有体积提示仍在，不影响构建 |
| `tests/backend/verify_complete_site.py`（容器） | 创建、旧站无写入默认、栏目保留、字段校验、修订号/并发409、ACL/CSRF/锁定、三种图片、体积/像素限制、跨会议/会话拒绝、同名文件夹回归、发布/撤回图片权限 |
| `tests/backend/verify_complete_rendering.py`（容器） | 递归三级导航ACL、父节点隐藏、分隔符、显隐过滤、转义/HTML清洗、英文回退、原生入口状态、禁用/外部入口不泄漏原生重复导航、旧模板路由 |
| `node tests/browser/verify_complete_editor.cjs` | 真实编辑保存/重开、中英文、列表增删排序显隐、图片上传预览移除、409/403保留草稿、重新载入确认、默认三模板、320/390px无溢出与标签不换竖行 |
| `node tests/browser/verify_complete_public.cjs` | 真实创建/上传/发布、超过1MiB上传穿过Nginx、桌面悬停和键盘/手机下拉、双语内容、显隐过滤、320/390/760/1440px、撤回后图片拒绝/登录跳转 |
| `node tests/browser/verify_complete_mobile.cjs` | 使用实际CSS，320/390/760px中文/英文登录按钮可读回归 |
| `tests/backend/verify_complete_business.py`（容器） | 真实报名和摘要投稿HTTP提交、后台记录、撤回阻止参会者；仅内存邮件 |
| `tests/backend/verify_site_builder.py`（容器） | 原有六页、注册、私密草稿、委托管理、原生导出/附件权限、默认首页、清洗、自定义CSS等回归 |
| `node tests/browser/verify_workspace_creation.cjs` | 实际组件填写并提交新默认模板、草稿与匿名拒绝 |
| `node tests/browser/verify_builder_browser.cjs` | 旧体验站4的编辑/预览/发布/公开列表/撤回/语言和响应式 |
| `node tests/browser/verify_session_language.cjs` | 登录状态、退出、身份不泄漏、语言持久化和表单输入保留 |

完整体验站61另经真实浏览器验证：9个主导航、4条示例嘉宾、4条单位、实际日程内页可访问、390px无横向溢出。公开站和编辑器浏览器测试均无pageerror。上游摘要表单在构造作者对象时有SQLAlchemy警告，最终摘要及作者提交成功；未修改上游。

测试脚本在finally中清理临时用户及会议（软删除）。旧浏览器回归复用原有体验站4；永久示例61由host-a拥有，工具`seed_complete_demo.py`重复运行只返回原记录，不覆盖已有演示内容。

## 源码与运行

- 后端：`worker/extension/yujian_site/site_content.py`、`blueprint.py`、`__init__.py`。
- 展示：`display.py`、`templates/complete-conference.html`、`portal/complete-conference.css`与`.js`。
- 编辑器：`frontend/src/SiteContentEditor.vue`、`App.vue`，构建产物`portal/ui-dist/`。
- 部署：现有Docker挂载不变；Python更新重启Web/Celery/Beat，图片代理配置已验证并reload。站点仍仅localhost开放。

容器测试命令示例（其余Python脚本替换文件名）：

```powershell
docker compose -p yujian-indico-v1 cp tests/backend/verify_complete_site.py indico-web:/tmp/verify_complete_site.py
docker compose -p yujian-indico-v1 exec -T indico-web /opt/indico/.venv/bin/python /tmp/verify_complete_site.py
```

独立只读复核发现的同名附件目录问题已经修复并复核关闭。没有尚未处理的实质性复核问题。

## 已知边界

发布站和草稿预览仍使用同一份内容；发布后保存立即影响公开站。如需编辑后再公开，先撤回。原生自定义CSS/主题的显式选择仍走原生显示；当前模板选择不清除用户的这类设置。未实现每次编辑的历史版本、图片未引用文件自动清理、独立子域名自动分配或完整内页的双语内容管理。当前上传图片即使从页面移除，仍保留于原生附件存储，后续可由管理者统一管理。
