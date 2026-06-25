$ErrorActionPreference = "Stop"

$StateDir = "D:\relief_story_state"
$ModelConfig = "D:\relief_story_agent_config\models.json"
$HostAddress = "127.0.0.1"
$Port = 8891

python -m relief_story_agent.server `
  --host $HostAddress `
  --port $Port `
  --state-dir $StateDir `
  --model-config $ModelConfig `
  --max-workers 2 `
  --lease-seconds 300
