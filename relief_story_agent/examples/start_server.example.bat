@echo off
setlocal

set "PROJECT_ROOT=%~dp0..\\..\\"
set "PYTHONPATH=%PROJECT_ROOT%;%PYTHONPATH%"
set "STATE_DIR=%PROJECT_ROOT%relief_story_state"
set "MODEL_CONFIG=%PROJECT_ROOT%relief_story_agent\examples\model_config.local.example.json"
set "HOST=127.0.0.1"
set "PORT=8891"
set "COMFYUI_ENDPOINT=http://127.0.0.1:8188"

if not exist "%STATE_DIR%" mkdir "%STATE_DIR%"

python -m relief_story_agent.server ^
  --host %HOST% ^
  --port %PORT% ^
  --state-dir "%STATE_DIR%" ^
  --model-config "%MODEL_CONFIG%" ^
  --comfyui-endpoint "%COMFYUI_ENDPOINT%" ^
  --max-workers 2 ^
  --lease-seconds 300 ^
  --recovery-poll-seconds 5
