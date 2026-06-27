@echo off
chcp 65001 >nul
title DrugDesign Agent Backend

cd /d "%~dp0\backend"

echo =========================================
echo  DrugDesign Agent Backend 启动脚本
echo =========================================
echo.

REM 检查 .env 文件是否存在
if exist "..\.env" (
    echo [INFO] 加载环境变量 .env ...
    for /f "tokens=1,* delims==" %%a in ('type "..\.env" ^| findstr /v "^#" ^| findstr /v "^$"') do (
        set "%%a=%%b"
    )
    echo [OK] 环境变量已加载
) else (
    echo [WARNING] 未找到 .env 文件，使用默认配置
    echo [HINT] 复制 .env.example 为 .env 并配置 KIMI_API_KEY
    echo.
)

REM 检查 KIMI_API_KEY
if "%KIMI_API_KEY%"=="" (
    echo [WARNING] KIMI_API_KEY 未设置，AI 聊天功能将不可用！
    echo [HINT] 在 .env 文件中设置 KIMI_API_KEY
    echo.
    timeout /t 3 /nobreak >nul
) else (
    echo [OK] KIMI_API_KEY 已配置
)

echo.
echo [INFO] 启动 Flask 后端...
echo [INFO] 端口: %FLASK_PORT%
echo.

"D:\anaconda3\envs\drugdesign\python.exe" -m backend.app

if errorlevel 1 (
    echo.
    echo [ERROR] 启动失败！请检查：
    echo   1. Anaconda 环境路径是否正确
    echo   2. 依赖包是否安装完整
    echo   3. 端口 %FLASK_PORT% 是否被占用
    echo.
    pause
)
