@echo off
chcp 65001 >nul
echo ============================================
echo  Math Portal - Sync from source repos
echo ============================================
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0_sync_from_source.ps1"
echo.
pause
