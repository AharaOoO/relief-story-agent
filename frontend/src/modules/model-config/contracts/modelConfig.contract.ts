export type ModelProfile = {
  profile_id: string
  provider: string
  model: string
  api_key_env: string
  status: 'configured' | 'missing_key' | 'unknown'
}

export type StageBinding = {
  stage: string
  profile_id: string
  required: boolean
}
