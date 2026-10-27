# 报名、投稿评审与参会中心（2026-10-15）

## 本轮交付

网站工作台的“报名与投稿管理”进入 `/conference/<会议ID>/operations/`。主办方可查看报名人数、待审核人数、收到稿件与待处理稿件，切换报名/投稿标签，再进入实际表单配置、字段编辑、名单审核、导出、征稿设置及审稿管理。

个人中心新增 `/participation/`，集中显示当前账号的报名、稿件和未完成审稿任务，支持搜索、状态筛选和中英文切换。门户账户菜单、会议网站和工作台均有“我的参会”入口；旧日程入口 `/user/dashboard/?legacy=1` 保留。

报名表、原生 React 字段编辑器、报名名单/详情、征稿后台、稿件列表/详情、审稿列表及相关弹窗沿用原生业务，包入遇见科技工作台。没有新增一套报名或稿件数据库，也没有把高级表单改写成另一套 Vue 业务实现。

## 使用方法

1. 主办方登录后进入“我的会议”，打开需要管理的网站，点击“报名与投稿管理”。
2. 在报名管理中进入“管理报名”，创建报名表，配置开放时间、审核方式及字段；开放后参会者从会议网站报名。
3. 在“名单与导出”中审核报名、查看详情及导出。页面统计读取实际报名状态。
4. 在投稿与审稿中配置征稿时间、专题及审稿角色。审稿人在“我的参会 → 审稿任务”进入分配给自己的专题；提交评审后，该稿件从待审数量中扣除，主办方仍需作出录用或拒绝决定。
5. 参会者在“我的参会”查看报名及稿件状态，并进入原生详情、允许的修改入口或已启用的参会凭证。

示例入口：<http://localhost:12880/conference/61/operations/>（需要会议完整管理权限）；个人入口：<http://localhost:12880/participation/>。示例会议61不接收实际报名或缴费。本轮没有更改会议22或61的业务数据、首页或外观。

## 数据与权限

- 聚合接口只读，响应 `Cache-Control: no-store`。办会管理要求完整会议管理权限；参会中心要求有效登录账号，不接受客户端指定其他用户。
- 报名按原生账号关联查询；邮件报名记录由原生系统的账号关联流程处理。稿件按提交人或已关联作者查询，并继续检查原生所有权和会议访问权限。
- 不返回报名 UUID、凭证 UUID、他人邮箱或审稿意见。私密草稿、撤回、删除或禁用功能继续受原生权限限制。
- 审稿任务按真实评审权限、专题及原生未审数量显示；管理员身份本身不算审稿任务。已提交评审在主办方作决定前就扣除。
- 锁定会议可以查看摘要，原生修改限制保留。仅有报名审核等分项权限的工作人员保留可用的原生入口，不展示需要完整管理权的返回链接或无权使用的功能标签。
- 原生表单 DOM、CSRF、JavaScript 初始化、确认和验证逻辑保留；AJAX 响应仍为原生片段。提示消息只渲染一次。

## 验证记录

| 检查 | 结果 |
| --- | --- |
| `tests/backend/verify_business_workspace.py`（容器） | 通过：真实报名/投稿、私有数据隔离、关联作者、评审角色、审批状态、原生完整链接、禁用/撤回/锁定及有限权限 |
| `tests/backend/verify_business_lifecycle.py`（容器） | 通过：报名待审核 → 审批成功 → CSV包含实际报名；提交评审 → 待审数量扣除 → 录用并生成 contribution；新工作台状态同步 |
| `tests/backend/verify_native_business.py`（容器） | 通过：18次实际页面检查，表单/初始化/CSRF、唯一提示容器、分项工作人员导航、AJAX片段及非业务页面排除 |
| `node tests/browser/verify_business_workspace_ui.cjs` | 通过：真实记录、搜索/状态筛选、中英文、错误重试、禁用提示、按钮文字和图标尺寸，320/390/1440px无页面横向溢出 |
| `node tests/browser/verify_native_business_ui.cjs` | 通过：15个原生页面及配置/投稿弹窗，React字段编辑/报名表加载、原生约束保留；审稿操作按钮对比度≥4.5；1440/390/320px无页面横向溢出，无浏览器脚本错误 |
| `tests/backend/verify_complete_site.py`、`tests/backend/verify_appearance_api.py`（容器） | 通过：完整建站、图片/附件权限、修订冲突与并发、十二种外观保存/预览及旧模板回归 |
| `node tests/browser/verify_workspace_ui.cjs`、`node tests/browser/verify_user_frame.cjs`、`node tests/browser/verify_complete_mobile.cjs` | 通过：原目录/工作台、个人资料及旧记录、中英文、输入保持与移动端回归 |

截图保存在 `../output/business-operations-*.png`、`business-participation-*.png` 及 `native-business-*.png`。已查看工作台、报名记录、原生字段编辑、审稿详情和投稿弹窗的实际截图；修正了按钮文字同色、统计图标压缩、手机弹窗偏移、正文过窄和图片上传按钮挤压。

独立代码复核发现已评审任务未及时扣除，已改用原生未审计数，并通过“评审提交后、录用前”断言验证。补充核验分项工作人员导航与唯一提示容器。截图检查发现原生文字型审核按钮被误设实色背景（对比度1.76），现保留原生按钮类型并使用品牌文字色，对比度检查通过。

容器验证可直接从 PowerShell 运行，例如：

```powershell
Get-Content tests/backend/verify_business_workspace.py | docker compose -p yujian-indico-v1 exec -T indico-web /opt/indico/.venv/bin/python -
Get-Content tests/backend/verify_business_lifecycle.py | docker compose -p yujian-indico-v1 exec -T indico-web /opt/indico/.venv/bin/python -
Get-Content tests/backend/verify_native_business.py | docker compose -p yujian-indico-v1 exec -T indico-web /opt/indico/.venv/bin/python -
node tests/browser/verify_business_workspace_ui.cjs
node tests/browser/verify_native_business_ui.cjs
```

测试业务写入在独立 `make_app` 进程中使用 `locmem` 邮件后端，临时账号和会议在退出时标记删除。浏览器业务表单测试不直接提交到真实 SMTP 服务。测试运行时不要重启容器，以免中断清理；本轮中断的一组临时闭环记录已单独核验并清理。

最终检查：本轮四类业务测试账号及其会议均为零条未删除记录，遗留的临时原生预览会议113及三名测试账号已清理；会议22和61仍存在。六个 Compose 服务运行中，首页及新版静态资源返回200，未登录访问参会中心正常进入登录页。

## 源码与边界

后端摘要在 `worker/extension/yujian_site/business.py`，路由在 `blueprint.py`，前端在 `frontend/src/BusinessWorkspace.vue` 和 `App.vue`。原生页面通过 `customization/templates/core/events/` 继承与 `portal/native-business.css/js` 适配，未修改上游源码。

目前主办方摘要只显示最近20篇稿件，完整名单、分页和导出使用原生页面；个人历史在服务端按账号查询后载入，数量很大时需要增加分页。接口不为浏览器提供任何新的身份或令牌能力。

本轮未接入自动支付、对账、开票或独立域名部署，企业邮箱实际收件仍需独立确认。现有高级设置保留原生控件，不能视为全部重新实现了业务界面。

原生摘要表单在测试中会输出 `EventPerson not in session` SQLAlchemy 警告；实际提交、评审及录用流程通过，未为消除日志提示修改上游代码。构建仍有现有 Element Plus 主包体积提示，未增加拆包或依赖。
