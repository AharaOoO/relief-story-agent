import { endpointPaths } from '../../../shared/api/endpointPaths'
import { postJson, requestJson } from '../../../shared/api/httpClient'
import type { ModelProfile } from '../contracts/modelConfig.contract'

export function fetchModelProfiles(): Promise<{ profiles: ModelProfile[] }> {
  return requestJson<unknown>(endpointPaths.configModels).then(
    normalizeModelProfilesResponse,
  )
}

export function validateModelConfig(): Promise<{ ready: boolean; blockers: unknown[] }> {
  return postJson(endpointPaths.configValidate, {})
}

export function runModelCheck(payload: {
  real_run: boolean
}): Promise<{ ready: boolean; checks: unknown[] }> {
  return postJson(endpointPaths.modelCheck, payload)
}

export function normalizeModelProfilesResponse(
  value: unknown,
): { profiles: ModelProfile[] } {
  if (!value || typeof value !== 'object' || !('profiles' in value)) {
    return { profiles: [] }
  }

  const profiles = (value as { profiles?: unknown }).profiles
  if (Array.isArray(profiles)) {
    return { profiles: profiles as ModelProfile[] }
  }

  if (!profiles || typeof profiles !== 'object') {
    return { profiles: [] }
  }

  return {
    profiles: Object.entries(profiles).map(([profileId, profile]) => {
      const record =
        profile && typeof profile === 'object'
          ? (profile as Record<string, unknown>)
          : {}
      const baseUrl = String(record.base_url ?? '')

      return {
        profile_id: profileId,
        provider: inferProvider(baseUrl, profileId),
        model: String(record.model ?? ''),
        api_key_env: String(record.api_key_env ?? ''),
        status: record.secret_configured ? 'configured' : 'missing_key',
      }
    }),
  }
}

function inferProvider(baseUrl: string, profileId: string): string {
  const source = `${baseUrl} ${profileId}`.toLowerCase()

  if (source.includes('gemini') || source.includes('google')) {
    return 'Google Gemini'
  }
  if (source.includes('deepseek')) {
    return 'DeepSeek'
  }
  if (source.includes('openai')) {
    return 'OpenAI compatible'
  }
  return 'Custom'
}
