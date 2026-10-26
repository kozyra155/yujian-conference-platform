# 报名投稿与参会工作台

用户在缺口清单后明确“继续”，按已建议的优先级完成报名管理、投稿审稿和参会者个人中心。保持现有蓝白工作台、Element Plus及原生业务实现，避免复制数据模型或绕过权限。

## 用户流程与边界

主办方网站工作台新增“办会管理”入口到 `/conference/<id>/operations/`，展示会议报名表、人数/待审核状态、稿件状态及配置/名单/导出/审稿管理入口。实际新建表单、字段编辑、审核、导出、审稿分配、录用仍用原生页面和接口；这些操作页面包入统一工作台并完善响应式。不得新增不可靠的支付状态、收费通道或发送测试邮件。

参会者 `/participation/` 展示当前登录用户的报名、稿件及实际审稿任务；原 `/user/dashboard/` 保持主办方列表，旧参会日历 `/user/dashboard/?legacy=1` 保留。新侧栏“我的参会”从门户登录下拉、Vue工作台和原生工作台均可进入。状态使用原生枚举并双语显示；查询支持关键字和状态筛选，统计只取当前用户可见记录。无记录有明确空态和浏览会议入口。草稿/撤回会议继续仅完整管理者可访问，不通过新聚合列表泄漏标题/稿件/报名信息。

## 私有只读接口

新增 `worker/extension/yujian_site/business.py` 只负责序列化和查询，blueprint复用RHAccount/RHManaged、响应no-store。

`GET /api/conferences/<id>/operations` 返回：

```json
{"event":{"id":61,"title":"会议","url":"/event/61/","builder_url":"/conference/61/","locked":false},
 "features":{"registration":true,"abstracts":true},
 "registration":{"total":0,"pending":0,"forms":[{"id":1,"title":"报名表","state":"open","state_label":"开放中","count":0,"pending_count":0,"url":"/event/61/manage/registration/1/","settings_url":"/event/61/manage/registration/1/edit","fields_url":"/event/61/manage/registration/1/form/","list_url":"/event/61/manage/registration/1/registrations/","public_url":"/event/61/registrations/1/"}],"links":{"manage_url":"/event/61/manage/registration/","create_url":"/event/61/manage/registration/create"}},
 "submission":{"state":"closed","state_label":"尚未开放","total":0,"pending":0,"counts":{},"recent":[{"id":1,"number":1,"title":"稿件","state":"submitted","state_label":"已提交","submitter":"作者","submitted":"2026-10-15T00:00:00+00:00","url":"/event/61/manage/abstracts/1/"}],"links":{"manage_url":"/event/61/manage/abstracts/","list_url":"/event/61/manage/abstracts/list","settings_url":"/event/61/manage/abstracts/","reviewing_url":"/event/61/manage/abstracts/","review_settings_url":"/event/61/manage/abstracts/","tracks_url":"/event/61/manage/"}}}
```

links值必须核对原生实际路由，由后端统一生成，不保留示例里可能不适合直接GET的settings对话框URL。对话框POST/GET碎片入口不要当整页导航，改用包含真实配置按钮的父页面。recent默认最近20条（说明“最近稿件”，全部稿件走原生完整列表），完整报名名单/分页/导出走原生，不把整个注册名单复制到新API。禁用的功能返回enabledfalse与零/空数据，清楚提示先在原生功能配置启用，不能直接展示404链接。锁定会议可GET只读、写操作沿用原生拒绝。

`GET /api/participation/` 返回 `{registrations,submissions,reviews}`：

```json
{"registrations":[{"id":1,"event_id":61,"event_title":"会议","event_url":"/event/61/","start":"2027-10-20T01:00:00+00:00","end":"2027-10-22T09:00:00+00:00","location":"武汉","form_title":"参会报名","state":"complete","state_label":"报名成功","url":"/event/61/registrations/1/","can_modify":false,"ticket_url":null}],
"submissions":[{"id":1,"event_id":61,"event_title":"会议","title":"稿件","number":1,"state":"submitted","state_label":"已提交","url":"/event/61/abstracts/1/","can_edit":false}],
"reviews":[{"event_id":61,"event_title":"会议","url":"/event/61/abstracts/reviewing/","tracks":[{"id":1,"title":"专题","url":"/event/61/abstracts/reviewing/1/","count":0}]}]}
```

报名按原生当前用户或已验证邮箱所有权（若采用邮箱必须只取验证邮箱，禁止客户端user_id）；稿件按submitter或nativeuser_owns已关联作者，且can_access，再过滤平台托管/未删除/事件可访问/功能启用。退回/撤回等非删除记录仍可显示真实状态。不要返回注册UUID/token、他人邮箱、审稿意见、作者身份泄漏或公开API缓存。ticket_url仅在原生允许显示且状态允许时提供，不伪造凭证。审稿只展示原生允许review的实际专题/任务，不给普通参会者评审入口。无任务空数组，不能以全局管理员身份推出用户已分配的审稿任务。查询不能扫描所有平台会议逐条判断全部注册数据，应以用户/作者/权限关系缩小候选并预加载关联；记录规模较小时前端筛选即可，文档注明后续分页界限。

## 展示与原生页面融合

Vue新 `BusinessWorkspace.vue` 支持mode operations/participation、eventId、language。根App.vue复用现有外壳，在对应mode挂载；新的组件局部样式不污染门户或原生React表单。组织管理采用报名/投稿审稿两个标签；顶部实际统计、报名表卡片/表格、最近稿件列表、明确的配置/审核/导出入口。参会中心采用报名/我的稿件/审稿任务三个标签，筛选与搜索、原生详情链接、返回会议链接，关键状态带文字。

原生业务页面通过自定义Jinja继承原模板包壳，保留完整content DOM、bundles、JS初始化、CSRF和错误/确认/锁定行为。只作用于平台托管会议的registration/abstracts整页；AJAX对话框和JSON碎片不包壳。管理与参会者页面使用不同标题/导航，提供回办会管理/我的参会/会议网站入口。不能在HTML未准备好时移动React根节点或复制字段。仍允许内嵌原生多步骤表单，不声称所有流程已用Vue重写。

## 验收

临时普通主办方、参会者、其他用户、审稿人/专题构造真实原生报名和摘要。通过真实HTTP提交报名/稿件，验证聚合数据只属自己、管理者实际人数、审核前后状态同步、后台名单导出和审稿入口可访问。模板包装需原生表单保持正常提交/对话框初始化。测试关邮件外发，仅locmem；不改变61/22和真实已有表单。新接口先写失败测试，再实现。桌面与320/390px截图人工检查，登录/权限/撤回/CSRF/锁定、完整建站旧测试回归，最后清理临时数据并独立复核。
