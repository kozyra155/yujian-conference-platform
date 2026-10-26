# 会议预制外观

用户要求参考CASCONF外观管理截图，将多种预制外观套用于遇见科技会议网站。实际访问 https://yunjisuan221.casconf.cn/platform/config/exterior 跳转403，公开首页显示未发布；公开JS只证实外观管理/页面模板结构，无法读取该账号的模板HTML/CSS。实现应如实称“按截图复现”，不得称已导出原十二套源码，不导入第三方账号脚本与品牌素材。

采用现有完整会议模板上的两种真实布局×六种配色。方案比独立复制十二套HTML更容易保持已有内容/权限一致，比只改颜色更符合截图的两种布局差异。选择器呈现十二张本地代码缩略图，选择、实际会议内容预览、保存；切换不改会议文字/图片/菜单/报名数据。新旧会议不自动更换布局或配色。

## 数据与接口

现有content.theme增加 `layout`，枚举 `simple-1`/`simple-2`，默认simple-1；accent保持旧值，未填保持#fa7d4b。GET content旧数据深合并theme后返回layout默认值，不持久化。允许旧客户端仅传accent，验证时补layout默认值。

GET `/api/conferences/<id>/content` wrapper增加 `appearances`，十二条 `{id,name,name_en,layout,accent}`，从插件新文件appearances.py统一导出。颜色橙#fa7d4b、红#d94a45、紫#8550ad、蓝#3f67c8、深蓝#293d78、绿#488b35；id simple-1-orange/simple-2-orange等。管理员仍能手动选自定义accent，不把任意色误认为预制外观。

POST `/api/conferences/<id>/appearance-preview` 接收 `{theme:{layout,accent}}`，RHManaged+原生CSRF+锁定检查，严格验证，不写设置/修订/菜单。直接调用 `render_conference(event, theme_override=theme)`，强制完整模板渲染，返回私有no-store HTML；使用当前服务端已保存会议内容预览，明确说明未保存的文字不会出现。公开渲染所有真实权限检查继续保留。模板htmliframe预览用srcdoc sandbox="allow-scripts allow-same-origin"不允许表单/弹窗/顶层跳转，插入base href当前origin保持资源路径；iframe内脚本来自我们同源已清洗页面。需拦截预览内普通链接避免导航离开预览，或sandbox不允许外部导航并在说明中明确只预览当前页面。允许iframe ownnav为同origin仍不改主窗口。

## 展示

simple-1保留大横幅、横向导航、正文+侧栏结构。simple-2为桌面左侧固定宽度的站点导航，右侧上方横幅、下方正文，信息侧栏内容在正文后以网格呈现；不是同一布局只换色。手机两者使用现有折叠导航，内页/业务入口与权限不变。class由严格枚举生成 `appearance-simple-1` / `appearance-simple-2`。所有强调色（标题、日期、活动链接、选中导航、按钮）统一读取accent，并用深色前景/边框保持可读，横幅/页脚深蓝仍保留。

## 管理

在SiteContentEditor的模板选择后、横幅表单前加入AppearancePicker，标题“预制外观”，按两种布局分组显示六种色，真实缩略图体现对应布局。选择卡片只改当前theme；保存沿用同一份content与修订号，不产生另一份状态。保留现有模板选项、上传、未保存提示、409/403行为。预览按钮使用POST只读接口，弹窗支持桌面/手机视口切换；保存按钮沿用现有首页设计保存。旧academic/industry站点说明选择预制外观后需使用完整学术模板并保存才应用；选择卡片可自动改本地template=academic-full并提示，不保存不改变公开站。自定义accent自动取消预设选中但保留layout。

## 验收

先写失败测试，再实现。后端验证12种catalog、layout默认旧数据兼容、非法布局/注入拒绝、预览无写入（revision/template/页面数）、跨账号/CSRF/锁定；前端临时会议实际选色选布局、预览不保存、保存持久化、旧内容和栏目不变、自定义色、手机无溢出、键盘选择。真实浏览器截simple1/simple2桌面/手机以及主题选择器，对照确认两种布局有实际差异。运行完整建站后端/编辑器/公开回归。临时数据清理，不修改22/61。独立代码复核后交付现有体验站管理入口。
