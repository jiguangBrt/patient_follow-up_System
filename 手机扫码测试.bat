@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set "PUBLIC_URL_FILE=.local\server-public-url.txt"
if not defined PUBLIC_BASE_URL (
    if not exist "%PUBLIC_URL_FILE%" (
        echo 尚未配置公网入口。
        echo 请在 .local\server-public-url.txt 中填写已部署站点的 HTTPS 地址，不带末尾斜杠。
        echo 本地热点测试请使用“局域网扫码测试.bat”。
        pause
        exit /b 1
    )
    for /f "usebackq delims=" %%U in ("%PUBLIC_URL_FILE%") do set "PUBLIC_BASE_URL=%%U"
)
echo 正在检查公网随访系统：%PUBLIC_BASE_URL%/
powershell -NoProfile -Command "try { $u = [uri]$env:PUBLIC_BASE_URL; if ($u.Scheme -ne 'https' -or -not $u.IsAbsoluteUri -or $u.UserInfo -or $u.Query -or $u.Fragment) { throw '入口必须为 HTTPS 站点地址' }; $health = Invoke-RestMethod -Uri ($env:PUBLIC_BASE_URL.TrimEnd('/') + '/health') -TimeoutSec 10; if ($health.status -eq 'ok') { exit 0 } } catch { Write-Host $_.Exception.Message }; exit 1"
if errorlevel 1 (
    echo 公网入口暂不可用，请检查地址和网络。不会改为本地数据库生成二维码。
    pause
    exit /b 1
)
echo 请使用服务器医生账号登录，账号说明见 .local\server-access.md。
echo 在公网后台新增虚构患者，再点击“建档二维码 / 重印”。
echo 手机扫码后提交的信息会保存到服务器数据库，与本机开发数据独立。
start "" "%PUBLIC_BASE_URL%/?role=doctor"
exit /b 0
