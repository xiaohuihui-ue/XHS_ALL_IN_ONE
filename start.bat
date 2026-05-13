@echo off
setlocal

set "ROOT=%~dp0"
set "BACKEND_HOST=127.0.0.1"
if not defined BACKEND_PORT set "BACKEND_PORT=8603"
if not defined FRONTEND_PORT set "FRONTEND_PORT=5173"
set "VITE_API_PROXY_TARGET=http://%BACKEND_HOST%:%BACKEND_PORT%"

echo Starting backend:  %VITE_API_PROXY_TARGET%
echo Starting frontend: http://127.0.0.1:%FRONTEND_PORT%
echo.

start "XHS_ALL_IN_ONE Backend" cmd /k "cd /d "%ROOT%" && python -m uvicorn backend.app.main:app --host %BACKEND_HOST% --port %BACKEND_PORT%"
start "XHS_ALL_IN_ONE Frontend" cmd /k "cd /d "%ROOT%frontend" && set "VITE_API_PROXY_TARGET=%VITE_API_PROXY_TARGET%" && npm run dev -- --host 127.0.0.1 --port %FRONTEND_PORT%"

endlocal
