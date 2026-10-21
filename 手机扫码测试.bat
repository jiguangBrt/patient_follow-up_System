@echo off
chcp 65001 >nul
setlocal
set "PYTHONUTF8=1"
cd /d "%~dp0"
set "HOTSPOT_IP="
for /f "usebackq delims=" %%I in (`powershell -NoProfile -Command "(Get-NetIPConfiguration -InterfaceAlias WLAN -ErrorAction Stop).IPv4Address.IPAddress"`) do set "HOTSPOT_IP=%%I"
if not defined HOTSPOT_IP (
    echo 未找到 WLAN 的 IPv4 地址。请先将电脑连接到手机热点。
    pause
    exit /b 1
)
echo 请在手机浏览器打开：http://%HOTSPOT_IP%:8011/
echo 医生账号：ddd001  密码：12345678
echo 姓名由医生填写后生成专属建档二维码。请保持电脑和此窗口运行。
echo 若电脑入口已经运行，请重新启动它，以更新二维码地址。
powershell -NoProfile -Command "try { $health = Invoke-RestMethod -Uri 'http://%HOTSPOT_IP%:8011/health' -TimeoutSec 2; $api = Invoke-RestMethod -Uri 'http://%HOTSPOT_IP%:8011/openapi.json' -TimeoutSec 2; if ($health.status -eq 'ok' -and $api.info.title -eq 'Patient Follow-up System MVP' -and ($api.paths.PSObject.Properties.Name -contains '/patients/{patient_id}/intake-link')) { exit 0 } } catch {}; exit 1" >nul 2>nul
if not errorlevel 1 (
    echo 手机测试入口已在运行，请直接使用上方地址。
    start "" "http://%HOTSPOT_IP%:8011/"
    exit /b 0
)
uv run --locked python scripts/start_review.py --host %HOTSPOT_IP% --port 8011 --public-base-url http://%HOTSPOT_IP%:8011 --open-browser
if errorlevel 1 (
    echo 启动失败，请检查上方提示。若 8011 已运行，可直接访问上方手机地址。
    pause
    exit /b 1
)
