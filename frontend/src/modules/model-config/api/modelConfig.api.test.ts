import { describe, expect, it } from 'vitest'
import { normalizeModelProfilesResponse } from './modelConfig.api'

describe('normalizeModelProfilesResponse', () => {
  it('converts backend profile dictionaries into table rows', () => {
    expect(
      normalizeModelProfilesResponse({
        profiles: {
          gemini_writer: {
            base_url: 'https://generativelanguage.googleapis.com/v1beta/openai',
            model: 'gemini-2.5-pro',
            api_key_env: 'GEMINI_API_KEY',
            secret_configured: false,
          },
        },
      }),
    ).toEqual({
      profiles: [
        {
          profile_id: 'gemini_writer',
          provider: 'Google Gemini',
          model: 'gemini-2.5-pro',
          api_key_env: 'GEMINI_API_KEY',
          status: 'missing_key',
        },
      ],
    })
  })
})
