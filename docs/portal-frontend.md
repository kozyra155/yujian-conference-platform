# 遇见科技首页改版记录

日期：2026-10-13。参考：https://www.casconf.cn/ 。本地地址：http://localhost:12880/ 。

## 改动

将 Indico 原生首页替换为遇见科技门户，沿用参考站的深蓝导航、1200px 内容宽度、蓝色功能展示区、黄色创建按钮、灰白交替分区、会议列表、菱形标题装饰和深蓝页脚。顶部导航和所有内容均使用遇见科技品牌。横幅网络图、标识和图标为本地 SVG，不依赖参考站素材或远程字体。

内容包含横幅介绍、六栏功能、最新会议查询、推荐会议、四步办会指引、可展开公告与底部入口。参考站的办会单位列表替换成使用指引，未填入未经确认的客户、合作机构、统计、联系方式或备案号。

首页只展示现有两场演示会议，分别位于上海和长沙。查询支持会议名称或地点、去除首尾空格、大小写与全角字符归一化；空结果有明确提示。横幅使用手动切换，移动导航支持展开、选中后收起及 Escape 关闭。

首页“创建会议”链接到 `/category/1/#create-event:conference:1`，调起原有创建表单。修正演示账户原先只有会议管理而没有创建权限的问题，仅添加演示目录的创建权限，不授予目录管理权限。未修改上游源码或其他项目容器。

## 验证与截图

- `node --check portal/app.js`：语法检查。
- `docker compose exec -T indico-nginx nginx -t`：Nginx 配置检查。
- `node tests/browser/verify_portal.cjs`：首页、关键词与地点搜索、空结果、导航、横幅、公告、登录后创建表单、两场会议链接及浏览器资源检查；320、390、760、1024、1440、1920px 宽度无横向溢出。
- `tests/backend/verify_demo.py`：两主办方可在演示目录创建会议，无目录管理权限；匿名不能创建；各会议权限隔离。
- `node tests/browser/verify_browser.cjs`：真实登录、各自会议管理、对方会议 403、匿名访问及栏目保存。

截图：桌面首页（本机历史验收文件，未上传：`../output/yujian-home-desktop.png`）、手机首页（本机历史验收文件，未上传：`../output/yujian-home-mobile.png`）、创建入口（本机历史验收文件，未上传：`../output/yujian-create-entry.png`）。验证结果保存在 `indico-demo/portal-verification.json`、`verification.json` 和 `browser-verification.json`。

## 当前范围

这是本地前端改版；会议详情、创建表单和管理界面仍主要使用 Indico 原有样式。前端列表为演示数据，新建会议尚未自动接入首页。创建向导、模板自动初始化、独立子域名、草稿发布以及报名支付不在本轮改动内，尚未正式上线。未进行自动无障碍审计或其他浏览器内核测试。

## 公司素材更新

2026-10-13 用户提供正式 Logo 和蓝绿色旋涡背景图，已按原图复制到 `portal/meet-logo.png`、`meet-background.png`。导航和页脚采用白底完整 Logo，英文品牌改为 Meet Technology。首页横幅保留原结构，改用左侧深色文字、右侧旋涡图片与渐变遮罩，功能区同步蓝绿色调。

登录页通过 Indico 官方模板扩展机制继承原页面，使用同一 Logo 和背景，并调整中文登录文案、输入框可访问名称及移动布局。原表单、CSRF 字段、登录处理与错误提示保持继承。底部保留较小的上游来源标识。平台原生页头及 favicon 也指向正式 Logo。

`node tests/browser/verify_brand.cjs` 验证用户素材正常加载、登录中文文案、CSRF 字段、真实主办方登录、其他会议管理 403；在 320、390、760、1024、1440px 宽度检查首页及登录页无横向溢出。`node tests/browser/verify_portal.cjs` 复测会议查询和创建表单等已有行为。

新版截图：首页桌面（本机历史验收文件，未上传：`../output/yujian-brand-desktop.png`）、首页手机（本机历史验收文件，未上传：`../output/yujian-brand-mobile.png`）、登录桌面（本机历史验收文件，未上传：`../output/yujian-login-desktop.png`）、登录手机（本机历史验收文件，未上传：`../output/yujian-login-mobile.png`）。图片是截图素材，高清屏清晰度受原始分辨率限制。
