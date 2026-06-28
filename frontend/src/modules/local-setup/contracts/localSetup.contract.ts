export type BootstrapInfo = {
  python?: string
  repo_root?: string
  state_dir?: string
  config_dir?: string
  default_server?: string
}

export type ComfyUIConnectionRequest = {
  endpoint: string
  workflow_api_path?: string
  timeout_seconds?: number
}

export type WorkflowDiscoveryResult = {
  path: string
  name?: string
  kind?: 'api_json' | 'litegraph' | 'unknown' | string
  compatible?: boolean
  supported?: boolean
  reason?: string
}
