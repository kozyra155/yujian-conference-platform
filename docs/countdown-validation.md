# 会议倒计时

入口：会议工作台 → 首页设计 → 会议倒计时（完整学术会议模板）。

- 开启“显示倒计时”并保存，会议首页内容区顶部显示独立横条。
- 实时显示天、时、分、秒；按服务器时间初始化，每秒重新计算剩余时间，浏览器日期或时区不同不会改变目标。
- 目标日期留空时，跟随会议开始日期（转换为北京时间）；也可选择其他日期。
- 目标统一为北京时间当日 00:00。到期后默认显示“会议已开始”，自选目标显示“目标日期已到”，不出现负数。
- 支持中英文、两种外观布局和手机排版。旧会议默认关闭，不改动已有会议数据；详情内页不重复显示横条。
- 数据仍保存在会议已有的 plugin_yujian_site / content 设置中，无需数据库迁移。

验证命令：

```powershell
Get-Content tests/backend/verify_countdown.py -Raw | docker compose -p yujian-indico-v1 exec -T indico-web /opt/indico/.venv/bin/python -
node tests/browser/verify_countdown_ui.cjs
```

后端校验覆盖默认关闭、旧配置兼容、非法日期、跨时区北京时间 00:00、默认日期跟随会议变更、自选目标、到期归零和仅首页显示。浏览器验收使用临时账号/会议，结束后清理，不发送真实邮件。

2026-10-19 验证通过：以上后端及浏览器脚本；现有 `tests/backend/verify_feedback_content.py`、`tests/backend/verify_complete_rendering.py`、`tests/backend/verify_appearance_rendering.py` 回归检查。前端 `npm run build` 成功（保留既有大分包体积提示）。浏览器覆盖保存/刷新、清空目标跟随会议、自选目标、服务器时间基准、逐秒更新、跨多日到期归零、中英文、关闭后保留设置；两种布局在 320、390、760、1024、1440 像素宽度无横向溢出。

截图与结果：`../output/countdown-1440.png`、`../output/countdown-390.png`、`../output/countdown-verification.json`。已人工查看桌面及手机截图。未改动已有会议的开关或日期；旧模板需要先切换至完整学术会议模板。
