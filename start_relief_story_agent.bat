@echo off
setlocal

set "PROJECT_ROOT=%~dp0"
set "PYTHONPATH=%PROJECT_ROOT%;%PYTHONPATH%"
set "STATE_DIR=%PROJECT_ROOT%relief_story_state"
set "MODEL_CONFIG=%PROJECT_ROOT%relief_story_agent\model_config.example.json"
set "HOST=127.0.0.1"
set "PORT=8891"

if not exist "%STATE_DIR%" mkdir "%STATE_DIR%"

echo Starting Relief Story Agent API...
echo Project root: %PROJECT_ROOT%
echo State dir: %STATE_DIR%
echo URL: http://%HOST%:%PORT%
echo.

python -m relief_story_agent.server ^
  --host %HOST% ^
  --port %PORT% ^
  --state-dir "%STATE_DIR%" ^
  --model-config "%MODEL_CONFIG%" ^
  --max-workers 2 ^
  --lease-seconds 300 ^
  --recovery-poll-seconds 5

if errorlevel 1 (
  echo.
  echo Server exited with an error. Check Python installation, dependencies, and model API key environment variables.
  pause
)
