@echo off
chcp 65001 >nul
setlocal
set "PYTHONUTF8=1"
cd /d "%~dp0"
echo 医生与学生权限隔离测试环境：http://127.0.0.1:8013/
echo 管理员 aaa001 / 医生 ddd001，初始密码均为 12345678。
echo 数据保存在 .local\issue_13_review，仅供虚构资料验收。
echo 学生账号请在医生的“学生与权限”页面开通。
echo 使用期间保持此窗口打开；如端口已占用，请先关闭上次测试窗口。
uv run --locked python scripts/start_review.py --data-dir .local/issue_13_review --port 8013 --open-browser
if errorlevel 1 pause
