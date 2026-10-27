@echo off
chcp 65001 >nul
setlocal
set "PYTHONUTF8=1"
cd /d "%~dp0"

echo 正在启动患者随访医生工作台...
echo 项目目录：%CD%
echo 统一登录：http://127.0.0.1:8010/
echo 医生账号：ddd001    密码：12345678
echo 在同一登录页选择患者、医生团队或管理员。
echo 管理员账号：aaa001  密码：12345678
echo.

powershell -NoProfile -Command "try { $health = Invoke-RestMethod -Uri 'http://127.0.0.1:8010/health' -TimeoutSec 2; $api = Invoke-RestMethod -Uri 'http://127.0.0.1:8010/openapi.json' -TimeoutSec 2; if ($health.status -eq 'ok' -and $api.info.title -eq 'Patient Follow-up System MVP' -and ($api.paths.PSObject.Properties.Name -contains '/clinical-documents')) { exit 0 } } catch {}; exit 1" >nul 2>nul
if not errorlevel 1 (
    echo 工作台已在运行，正在打开现有页面...
    start "" "http://127.0.0.1:8010/"
    exit /b 0
)

where uv >nul 2>nul
if errorlevel 1 (
    echo 未找到 uv。请先安装 uv，并重新打开此脚本。
    pause
    exit /b 1
)

if not exist "scripts\start_review.py" (
    echo 未找到 scripts\start_review.py，请将启动脚本放在完整项目的根目录。
    pause
    exit /b 1
)

echo 首次运行会自动准备依赖、验收数据库、账号和虚构样例，请稍候...
echo 数据保存位置：.local\issue_8_10_review
echo 服务就绪后会自动打开浏览器。使用期间请保持本窗口打开，按 Ctrl+C 停止。
echo.
uv run --locked python scripts/start_review.py --open-browser
set "launchExitCode=%errorlevel%"
if not "%launchExitCode%"=="0" (
    echo.
    echo 启动失败，请查看上方错误。若 8010 端口被其他程序占用，请先关闭该程序后重试。
    pause
)
exit /b %launchExitCode%
