# Linux 单机多项目部署

本项目使用独立 systemd 服务、Linux 用户、虚拟环境及数据目录。Nginx 共用 80 端口，按路径将流量分配到各项目；本项目使用 `/patientfollowup/`。此部署是无大模型的试用环境。本文的 `203.0.113.10` 仅为文档示例 IP，操作时替换为实际地址；当前服务器信息仅保存在被 Git 忽略的项目记忆中。

## 目录和服务

| 项目 | 位置 |
| --- | --- |
| 代码版本 | `/srv/apps/patientfollowup/releases/<版本>/` |
| 当前版本链接 | `/srv/apps/patientfollowup/current` |
| Python 环境 | 每个版本目录内的 `.venv/` |
| 配置与服务端密钥 | `/etc/patientfollowup/app.env`，禁止提交仓库 |
| 首次创建的试用账号 | `/etc/patientfollowup/initial-accounts.json`，仅 root 可读 |
| SQLite 数据库 | `/var/lib/patientfollowup/app.db` |
| 原件 | `/var/lib/patientfollowup/uploads/` |
| 每日备份 | `/var/lib/patientfollowup/backups/` |
| 应用服务 | `patientfollowup.service`，用户 `patientfollowup` |
| 应用监听 | `127.0.0.1:8101`，不直接对公网开放 |
| 项目 Nginx 路径规则 | `/etc/nginx/project-locations/patientfollowup.conf` |
| 共用 Nginx 站点 | `/etc/nginx/sites-available/projects` |
| 定时备份 | `patientfollowup-backup.timer` |

访问 `/patientfollowup` 会跳转到 `/patientfollowup/`。当前已启用公网 IP HTTPS，HTTP 自动跳转到 HTTPS；HTTPS 宿主根路径 `/` 返回 404，为其他项目保留。前端的接口、跳转、静态资源和 sessionStorage 键均适配部署前缀；API 文档位于 `/patientfollowup/docs`。

## 常用维护

以下命令在服务器执行：

```bash
systemctl status patientfollowup --no-pager
journalctl -u patientfollowup -n 100 --no-pager
systemctl restart patientfollowup
curl -fsS --resolve 203.0.113.10:443:127.0.0.1 https://203.0.113.10/patientfollowup/health
systemctl list-timers patientfollowup-backup.timer
systemctl start patientfollowup-backup.service
```

Nginx 的访问日志在共享服务器上；Uvicorn 不记录含患者 ID 的请求路径。不要将日志或备份放在 Nginx 可直接下载的目录。

备份通过 SQLite backup API 生成数据库快照，再与上传目录打包。当前备份保留在同一台机器，不构成异机灾难恢复；应定期下载至安全存储并监控磁盘容量。在持续上传期间，数据库与原件打包不是整个应用的原子快照；恢复前需核验文件与记录的一致性。

## 首次安装

1. 安装 `nginx`、`python3-venv`、`libgl1`、`libglib2.0-0`。
2. 从本地锁文件导出 Linux 兼容的依赖列表：

   ```powershell
   uv export --frozen --no-dev --no-hashes --no-emit-project --output-file .local/deployment-requirements.txt
   ```

3. 仅打包 `src/`、`migrations/`、`deploy/`、`alembic.ini`、`pyproject.toml`、`uv.lock`；导出的依赖文件在包内命名为 `requirements-deploy.txt`。排除缓存、`.env`、本机数据库、原件、Git 元数据及本地记忆文件。
4. 解压到 `/srv/apps/patientfollowup/releases/<版本>/`，在该目录首次执行 `DEPLOY_PUBLIC_BASE_URL=http://203.0.113.10/patientfollowup bash deploy/linux/install.sh`，将示例 IP 替换为实际地址；后续更新保留服务器现有环境配置。
5. 检查数据库迁移、服务、健康接口、账号登录、静态资源及上传/OCR。`install.sh` 不会重置已有试用账号。

安装脚本使用阿里云 PyPI 镜像，依赖版本来自锁文件。首次安装通过 `DEPLOY_PUBLIC_BASE_URL` 指定公开地址；改用域名或 HTTPS 时应修改服务器环境文件并重启服务，同时更新本地项目记忆。

## 后续更新与其他项目

### 从 Git 同步 main 并部署

服务器使用 `/srv/apps/patientfollowup/source` 作为 Git 源码仓库（分支为 `main`），每次部署建立独立的 Git worktree 版本目录，`current` 指向正在运行的版本。数据库、原件和配置继续使用上表中的独立位置。

已安装更新命令后，在服务器运行：

```bash
patientfollowup-update --check   # 拉取 main，显示最新提交与正在运行的提交，不切换服务
patientfollowup-update           # 准备并部署 main；已是同一提交时不会重复重启
git -C /srv/apps/patientfollowup/source status --short --branch
git -C /srv/apps/patientfollowup/current log -1 --oneline
```

这是手动更新入口，不会因 GitHub 有新提交就自动部署。请把功能分支合并进 `main` 后再运行。拉取有超时和重试，网络失败时保留正在运行的版本。源码仓库或正在运行的 worktree 有本地修改时，命令会停止；不会自动清除修改或强制覆盖分支。

更新时先准备依赖，依赖锁文件未变化则引用已有虚拟环境，变化时按 `uv.lock` 创建独立环境。代码与数据库迁移版本不同时，停止应用并备份数据，再执行迁移。新版本健康检查失败时自动切回旧代码并尝试启动旧服务；数据库不会自动降级，涉及不兼容迁移时应根据备份人工恢复。旧版本的虚拟环境可能被新版本引用，不能直接删除旧 release。

在另一台已经按本文安装好服务的服务器上，首次配置可执行：

```bash
git clone --branch main --single-branch --filter=blob:none <Git仓库地址> /srv/apps/patientfollowup/source
python3 -m venv /opt/patientfollowup-tools
/opt/patientfollowup-tools/bin/pip install uv==0.11.7 -i https://mirrors.aliyun.com/pypi/simple/
install -m 0755 /srv/apps/patientfollowup/source/deploy/linux/update-from-git.sh /usr/local/sbin/patientfollowup-update
patientfollowup-update --check
patientfollowup-update
```

公开仓库使用 HTTPS 读取即可。私有仓库应另行配置只读部署凭据，不要复制本机私钥，也不要把访问令牌写进仓库 URL。首次接管旧的非 Git release 前，应核对它与 `main` 的运行代码差异，保留尚未提交的服务器修复。

部署器脚本自身有变更时，待相应 PR 合并并更新后，再将 `current/deploy/linux/update-from-git.sh` 重新 `install -m 0755` 到 `/usr/local/sbin/patientfollowup-update`。

部署器的回归测试在 Linux root 下运行：`python3 tests/test_git_deploy.py`。测试使用临时 Git 仓库和模拟服务/网络命令，覆盖只检查、精确版本切换、重复执行、网络失败、脏工作区保护、依赖准备失败，以及迁移或健康检查失败回退，不操作实际应用数据。

- 更新代码使用新的 release 目录，数据和配置始终留在 release 之外。运行迁移前先备份，确认版本兼容再切换 `current`。
- Python 代码可切回旧 release，但数据库迁移不会随软链接自动回滚；恢复数据库须按迁移兼容性单独处理。
- 其他项目使用独立用户、数据目录和本机端口（例如 8102），再在 `/etc/nginx/project-locations/` 新建互不重叠的 location 文件。不要重复创建监听同一默认端口的站点，也不要抢占本项目端口或路径。
- 修改 Nginx 后先运行 `nginx -t`，通过后执行 `systemctl reload nginx`。
- 上传大文件还需要 Nginx 请求临时目录可写。Ubuntu 的 worker 用户为 `www-data`，`install.sh` 会将 `/var/lib/nginx/body` 设为该用户所有、权限 `0700`。若小请求正常而上传返回 HTML 500，检查 `/var/log/nginx/error.log` 是否出现该目录的 `Permission denied`；测试须包含接近 8 MB 的真实图片，以覆盖请求写入临时文件的路径。修改 worker 用户或临时目录时须同步权限，不要放宽为全员可写。
- 当前使用可信的公网 IP HTTPS，未配置域名，也不代表已经完成备案。仅用于受控试用；正式患者资料上线前需完成相应访问和数据保护安排。

## 公网 IP HTTPS 与自动续期

当前入口为 `https://203.0.113.10/patientfollowup/`。TLS 在共用 Nginx 入口终止，后端仍使用本机 HTTP 8101 端口；其他项目可以复用该 IP 的 HTTPS 入口。

- 使用免费 Let's Encrypt `shortlived` 公网 IP 证书，约 6 天有效，不能依靠人工偶尔续期。
- Certbot 独立环境：`/opt/certbot`，不复用业务环境。
- 证书和私钥：`/etc/letsencrypt/live/203.0.113.10/`，私钥仅留在服务器，不提交仓库。
- ACME HTTP-01 验证根目录：`/var/www/acme`；80 端口的 `/.well-known/acme-challenge/` 必须保持外网可达，不能被其他项目覆盖或强制跳到错误位置。
- HTTPS 站点模板：`deploy/linux/projects-https.nginx.conf`，其中 `__PUBLIC_IP__` 由切换脚本从服务器环境配置读取并替换。首次切换脚本：`deploy/linux/activate-https.sh`，必须先有有效正式证书才可执行。
- `certbot-renew.timer` 每天两次检查续期；部署 hook 成功续期后检查并重载 Nginx。
- 当前二维码基础地址已经在服务器配置为 `PUBLIC_BASE_URL=https://203.0.113.10/patientfollowup`。

```bash
systemctl status certbot-renew.timer --no-pager
systemctl list-timers certbot-renew.timer --no-pager
journalctl -u certbot-renew.service -n 50 --no-pager
openssl x509 -in /etc/letsencrypt/live/203.0.113.10/fullchain.pem -noout -issuer -dates
/opt/certbot/bin/certbot renew --cert-name 203.0.113.10 --dry-run --run-deploy-hooks --no-random-sleep-on-renew
```

已通过首次模拟续期和部署 hook 测试。应定期检查续期服务状态；更换公网 IP 时需重新申请匹配新 IP 的证书，不能直接复制旧证书沿用。Certbot 依赖维护和版本升级独立于业务代码更新。

## 手机公网扫码测试

双击仓库根目录的 `手机扫码测试.bat`，它会检查公网健康接口并打开公网医生登录页。第一次使用时，在被忽略的 `.local/server-public-url.txt` 中填写实际 HTTPS 地址（例如 `https://203.0.113.10/patientfollowup`，不带末尾斜杠）；也可以通过 `PUBLIC_BASE_URL` 环境变量指定。

使用服务器医生账号，在公网后台新增虚构患者并点击“建档二维码 / 重印”，手机可以使用移动数据扫码，提交后返回公网后台查看该患者资料。二维码由服务器 API 生成，包含当前 `PUBLIC_BASE_URL`。

本地、云端的数据库、认证密钥和二维码令牌独立，不能将本地二维码中的主机名手工替换为公网 IP。原热点测试入口保留为 `局域网扫码测试.bat`；`本地启动.bat` 继续使用本机数据库。登录说明、服务器地址及包含访问令牌的二维码图片均留在 `.local/`，不提交仓库。
