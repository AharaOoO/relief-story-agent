import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { routes } from './router'

function renderRoute(path: string) {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  const router = createMemoryRouter(routes, { initialEntries: [path] })

  return render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
}

describe('configuration guidance', () => {
  it('shows where to open the app and where to edit ports', async () => {
    renderRoute('/local-setup')

    expect(await screen.findByText('打开与端口')).toBeInTheDocument()
    expect(screen.getByText('Relief Story Agent Desktop.lnk')).toBeInTheDocument()
    expect(screen.getByText('http://127.0.0.1:5173')).toBeInTheDocument()
    expect(screen.getByText('http://127.0.0.1:8891')).toBeInTheDocument()
    expect(screen.getAllByText('后端 API / 端口').length).toBeGreaterThan(0)
  })

  it('explains model API key storage and prompt template paths', async () => {
    renderRoute('/model-config')

    expect(await screen.findByText('API key 保存方式')).toBeInTheDocument()
    expect(screen.getByText('Windows 用户环境变量')).toBeInTheDocument()
    expect(screen.getByText('提示词模板目录')).toBeInTheDocument()
    expect(screen.getByText('prompt_writer.default.md')).toBeInTheDocument()
    expect(screen.getByText('prompt_audit.default.md')).toBeInTheDocument()
  })
})
