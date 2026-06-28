import { normalizeApiError } from './apiError'
import { useUiStore } from '../store/uiStore'

type RequestOptions = RequestInit & {
  apiBaseUrl?: string
}

export async function requestJson<T>(
  endpoint: string,
  options: RequestOptions = {},
): Promise<T> {
  const apiBaseUrl = options.apiBaseUrl ?? useUiStore.getState().apiBaseUrl
  const url = endpoint.startsWith('http')
    ? endpoint
    : `${apiBaseUrl.replace(/\/$/, '')}${endpoint}`

  try {
    const response = await fetch(url, {
      ...options,
      headers: {
        'content-type': 'application/json',
        ...options.headers,
      },
    })

    const text = await response.text()
    const data = text ? JSON.parse(text) : null

    if (!response.ok) {
      throw normalizeApiError(data, {
        endpoint,
        statusCode: response.status,
      })
    }

    return data as T
  } catch (error) {
    throw normalizeApiError(error, { endpoint })
  }
}

export function postJson<T>(endpoint: string, body: unknown): Promise<T> {
  return requestJson<T>(endpoint, {
    method: 'POST',
    body: JSON.stringify(body),
  })
}
