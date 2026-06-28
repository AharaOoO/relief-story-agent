import { StatusBadge } from '../../../shared/components/StatusBadge'
import type { ModelProfile } from '../contracts/modelConfig.contract'

const fallbackProfiles: ModelProfile[] = [
  {
    profile_id: 'chief_screenwriter',
    provider: 'Gemini',
    model: 'gemini-2.5-pro',
    api_key_env: 'GEMINI_API_KEY',
    status: 'missing_key',
  },
  {
    profile_id: 'deepseek_polish',
    provider: 'DeepSeek',
    model: 'deepseek-chat',
    api_key_env: 'DEEPSEEK_API_KEY',
    status: 'missing_key',
  },
  {
    profile_id: 'prompt_writer',
    provider: 'OpenAI compatible',
    model: 'gpt-5-mini',
    api_key_env: 'OPENAI_API_KEY',
    status: 'missing_key',
  },
]

export function ModelProfileTable({
  profiles = fallbackProfiles,
}: {
  profiles?: ModelProfile[]
}) {
  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th>Profile</th>
            <th>Provider</th>
            <th>Model</th>
            <th>Key Env</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {profiles.map((profile) => (
            <tr key={profile.profile_id}>
              <td>{profile.profile_id}</td>
              <td>{profile.provider}</td>
              <td>{profile.model}</td>
              <td>{profile.api_key_env}</td>
              <td>
                <StatusBadge
                  status={profile.status === 'configured' ? 'ready' : 'blocked'}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
