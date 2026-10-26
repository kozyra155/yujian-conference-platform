# 完整学术会议建站模板

用户已确认目标：一键创建完整会议网站，主办方可以独立维护；以 https://uavrs2026.casconf.cn/ 的横幅、下拉导航、双栏布局、嘉宾、动态和单位侧栏为参照，品牌为遇见科技。继续当前实现，无需再次设计确认。

## 数据与接口约定

沿用插件事件设置、原生 EventPage/MenuEntry、原生附件归档、权限与发布流程。模板值新增 `academic-full`，新建表单默认选中；`academic`/`industry` 保持原行为，已有会议不自动改内容。

`GET /api/conferences/<event_id>/content` 返回 `{template, revision, content, registration_url, submission_url}`。`PUT` 同地址接收 `{revision, content, template}`，template 仅允许 academic-full/academic/industry；成功返回同样结构，陈旧 revision 返回409。全部使用 RHManaged（登录、完整管理权限、锁定检查、原生CSRF），Cache-Control private,no-store。锁行后读取最新设置并校验 revision，避免多管理员覆盖。

`POST /api/conferences/<event_id>/assets` 接收 multipart 字段 `file`，返回201 `{url}`。图片限定 PNG/JPEG/WebP、5MiB、最大2000万像素，实际解码验证，不信任扩展名，不允许SVG。储存在原生隐藏附件文件夹，继承会议权限，撤回后匿名不可访问。图片上传不修改内容修订号。

content 结构如下；字段全可有默认值，保存时验证类型/数量/长度/URL，拒绝未知字段，不允许脚本或任意HTML。中英文字段分开维护，空英文回退中文。每条列表项必须 enabled:boolean。图片字段只允许本会议已存在且可访问的上传图片地址；普通链接允许http/https及安全站内绝对路径，submission外部地址额外允许mailto。

```json
{
  "banner":{"image":"","image_en":"","title":"","title_en":"","subtitle":"","subtitle_en":"","show_title":true},
  "theme":{"accent":"#fa7d4b"},
  "introduction_en":"",
  "sections":[{"key":"introduction","enabled":true},{"key":"speakers","enabled":true},{"key":"news","enabled":true},{"key":"notices","enabled":true},{"key":"venue","enabled":true}],
  "speakers":[{"name":"","name_en":"","affiliation":"","affiliation_en":"","topic":"","topic_en":"","image":"","enabled":true}],
  "news":[{"title":"","title_en":"","date":"2026-10-15","body":"","body_en":"","url":"","enabled":true}],
  "dates":[{"label":"","label_en":"","date":"","enabled":true}],
  "organizations":[{"title":"主办单位","title_en":"Organizers","enabled":true,"items":[{"name":"","name_en":"","image":"","url":"","enabled":true}]}],
  "contact":{"name":"","name_en":"","phone":"","email":"","address":"","address_en":"","enabled":true},
  "notices":{"text":"","text_en":"","enabled":true},
  "venue":{"description":"","description_en":"","enabled":true},
  "actions":{"registration":{"enabled":false,"mode":"native","url":""},"submission":{"enabled":false,"mode":"native","url":""}}
}
```

默认 speakers/news 空数组，dates 至少填会议日期，organizations 默认为主办单位/技术支持/产业支持/期刊支持四个空分组，不编造姓名、机构或已开通服务。GET 对旧会议返回非持久化的默认结构。内容保存 template=academic-full 时幂等补齐栏目，不覆盖/重命名原页面。新完整会议预置会议组织（组委会、专题召集人子栏目）、会议日程、注册缴费、会议投稿、会议酒店、考察活动、历届会议、联系我们；已有六页保留并补缺。

## 实际业务入口

完整模板启用原生 registration 与 abstracts 功能，但不自动开放收费/报名/投稿。返回原生报名 `/event/<id>/registrations/`、投稿 `/event/<id>/abstracts/`，以及后台管理链接；只有主办方明确开启 actions 时展示入口。原生报名有实际表单才显示可报名；投稿保留原生开放状态提示，禁止虚构支付成功。后台提供直达原生配置和外部链接模式。自动支付对账、开票不在本轮范围。

## 前端编辑

新增 `frontend/src/SiteContentEditor.vue`（含所需局部样式），由现有 App.vue 网站工作台挂载。标签“首页设计”，含横幅、首页模块排序/显隐、嘉宾、动态、重要日期、单位分组及Logo、联系信息、参会须知/酒店文本、报名投稿入口。每类项目可添加/删除/上移/下移，图片支持实际上传+预览+移除。英文内容可折叠展示。保存使用CSRF，错误信息保留草稿，409提示刷新而不覆盖，离开未保存提示。保存前预览展示上一次保存效果，明确提示。旧站主动选择完整模板后补充内容；不默默替换旧站。

## 公开展示

新增完整模板独立 SSR 模板及专属 CSS/JS。display.py 只在 template=academic-full 时选它，原显示保留。白底1200px居中，会议大横幅、横向下拉导航、左正文右300px侧栏、橙色栏目标题、深蓝页脚。banner有图片时按原图比例展示，show_title可隐藏重复标题。默认无图用项目现有科学背景；不会抓取/热链参考站图片。首页按 sections 顺序展示有效模块，无内容不留大空框。单位分组保持后台顺序。页面导航递归且每层检查 is_visible/can_access，隐藏/受限父节点的孩子不能泄露，支持鼠标/键盘/移动端。默认页、自定义CSS/主题回退行为保留。

中英切换采用data-zh/en与既有MeetPortal，内容字段服务端转义；介绍原生HTML继续sanitize_html。没有英文时保留中文，不伪装自动翻译。前台不包含管理API内容和隐藏条目。

## 验收

使用临时普通账号/会议验证默认完整模板创建、字段持久化、多语言、增删排序显隐、图片真实上传与撤回权限、409、CSRF、跨账号拒绝、锁定、恶意URL/文件拒绝、受限多级导航、原生入口可访问。回归已有 verify_site_builder.py / verify_builder_browser.cjs，桌面及320/390px截图人工查看。不修改会议22，不发送外部邮件。提供独立只读复核和具体测试记录。
