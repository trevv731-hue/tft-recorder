@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo   TFT 战绩统计助手 - Git 仓库更新
echo ========================================
echo.

set GIT="C:\Program Files\Git\cmd\git.exe"

if not exist %GIT% (
    echo [错误] 未找到 Git，请先安装 Git
    pause
    exit /b 1
)

echo [1/5] 配置 Git 用户信息...
%GIT% config user.email "trevv731@gmail.com"
%GIT% config user.name "trevv731-hue"

echo.
echo [2/5] 创建 legacy-v1 分支（保存旧 main）...
%GIT% branch -D legacy-v1 2>nul
%GIT% branch legacy-v1 origin/main
%GIT% push origin legacy-v1
if errorlevel 1 (
    echo [警告] legacy-v1 推送失败，可能已存在，继续...
)

echo.
echo [3/5] 创建新 main 分支（当前最终版）...
%GIT% checkout -B main
%GIT% add -A
%GIT% commit -m "feat: 最终版 - 海克斯评级+对手情报+性能优化"

echo.
echo [4/5] 强制推送新 main 到远程...
%GIT% push --force origin main

echo.
echo [5/5] 完成！
echo ========================================
echo.
echo 旧 main 已保存为 legacy-v1 分支
echo 新 main 已更新为当前最终版
echo.
echo 请前往 GitHub 仓库 Settings - Branches
echo 确认默认分支为 main
echo.
pause
