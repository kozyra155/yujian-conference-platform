# 2026-10-15 网站运行环境恢复

## 原因与证据

Windows C盘剩余空间为0。Docker Desktop后端在09:21:07 UTC记录 `There is not enough space on the disk`，随后引擎由running转为stopping并卡住；本机12880没有监听。机器内网IP仍为192.168.2.36。

## 已处理

- 将可重新下载的pip缓存完整迁到 `D:/works/yujian-conference-design/recovery/cache-backup/pip-20261015`，保留4068个文件，共1704290916字节；没有删除公司文件或会议卷。
- Docker常规重启超时后，仅结束失去响应的Docker进程并重启docker-desktop发行版、后台启动Docker Desktop。
- 使用 `docker compose -p yujian-indico-v1 up -d --no-recreate` 启动原有6个网站容器，保留原容器及持久卷。
- Compose及当前6个容器均设置 `restart: unless-stopped`。此设置在Docker引擎可运行时自动恢复服务；不能防止磁盘再次耗尽，也不会在Docker Desktop未启动时独立提供网站。

## 验证

`D:/python/python.exe tests/backend/verify_service_recovery.py` 检查Compose与实际容器重启策略、6个服务运行状态、本机/内网首页、登录页和会议61首页，均通过。验证HTTP请求绕过系统代理，以免将代理报错误认为应用响应。

`node tests/browser/verify_lan_access.cjs` 验证实际登录、我的参会、主办方工作台、创建入口及个人资料。数据库原生应用读取会议22/61成功，发布与公司收款状态保持原样。未执行全面数据完整性检查、真实扣款或外部邮件测试。

恢复后C盘剩余约3.6GiB，仍然偏少；需继续整理系统盘或规划Docker数据迁移。此次不迁移Docker数据库虚拟磁盘，不删除或清空持久卷。
