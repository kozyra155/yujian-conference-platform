# 1016 测试反馈修改与验证（2026-10-19）

入口：`/conference/create/` 创建，`/organizer/` 选择会议，工作台“站点设置”编辑基本信息，“首页设计”编辑模块，“设为栏目的内容”维护独立页面。

## 修改

- 创建及基本信息编辑新增45个会议领域、17个计划检索选项、主办单位、电话、国家省州市及详细地址；状态按时间计算。
- 基本信息使用行锁、数字版本和原生字段指纹，防止覆盖其他新编辑页或 Indico 原生后台的修改；保留未修改的富文本、第二联系电话和既有日程。兼容空主办方及多行简介。
- 保存错误展示具体字段路径；非法链接、超长文字、跨会议图片、过期版本均有反馈并保留当前草稿。
- 首页扩展为14个可排序模块，新增部分默认隐藏；嘉宾角色及1000字简介、委员会成员、单位300字介绍、每组20张图片支持选择、拖放及粘贴。
- 报名与投稿须知可以作为独立正文板块，并沿用真实入口和开放状态。联系信息支持文字格式、表格与独立图片集；富文本剥离图片和嵌入媒体，图片统一走归属校验的上传集。
- 新增征稿分组、产业技术需求、成果展示方案一、对接活动、参会对象与亮点；公开页面支持中文和英文，单个模块没有英文时继续显示中文。
- 产业意向分为技术合作、企业需求和投资落地三类，复用原生私密免费表单。保存启用时创建一次；关闭后阻止旧邀请链接提交；保留主办方手动关闭状态。登记信息可由主办方查看及完整CSV导出，不触发自动邮件或付款订单。
- 邮箱等待页面刷新后保持状态；补充Cookie异常恢复、完整验证链接继续及跨设备登录指引，缩小微信旧浏览器提示。

## 已执行验证

- `frontend/apiErrors.test.mjs` 与 `npm run build`。
- `worker/extension/metadata_selfcheck.py`、`metadata_api_selfcheck.py`：创建兼容、基本信息、原生修改冲突、并发、日程边界、换行与空资料。
- `verify_feedback_content.py`：持久化与公开展示、旧数据读取不写入、字段限制、图片归属、富文本及独立须知。
- `verify_feedback_editor.cjs`、`verify_feedback_metadata_ui.cjs`：实际创建编辑、批量上传、表格、模块保存、字段错误、冲突草稿、中英切换及移动布局。
- `verify_interests.py`、`verify_interests_ui.cjs`：三类实际提交、完整导出、访问权限、关闭及重新启用、邮件和财务隔离。
- `verify_conference_accounts.py`、`verify_conference_accounts_feedback.py`、`verify_conference_accounts_feedback_ui.cjs`：签名邮件、CAPTCHA、CSRF、全新浏览器、过期及伪造链接、等待状态和手机提示。
- `verify_complete_site.py`、`verify_complete_editor.cjs`、`verify_complete_public.cjs`、`verify_complete_rendering.py`、`verify_appearance_rendering.py`：原功能及外观回归。
- `verify_payments.py`：内存模拟的报名、到账、退款、开票申请及支付签名回调，无真实收付款。
- `verify_service_recovery.py`：六个服务和主要页面可访问。

浏览器截图及结果位于上级 `output/feedback-1016/`，另有 `output/feedback-*-*.png` 与 `output/interest-*.png`。验收均使用独立临时会议和账号，完成后清理其可见记录；未修改会议22、61、171。

## 尚未验证及暂缓

没有发送真实邮件、没有真实iOS微信内核环境，也没有执行真实收付款。用户确认原问题发生在直接点击邮件链接之后；需用一封新验证邮件在原手机实测，当前不能据基线通过宣称原始重复验证根因已解决。

前端构建仍有既有包体超过500kB提示；原生投稿测试有 SQLAlchemy SAWarning，业务断言通过。宣传横幅、转发收藏及成果展示方案二按反馈约定暂缓。
