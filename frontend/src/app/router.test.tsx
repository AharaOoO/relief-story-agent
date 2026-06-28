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

describe('router', () => {
  it.each([
    ['/local-setup', '本地环境检查'],
    ['/model-config', '模型配置'],
    ['/create-run', '创作任务'],
    ['/runs/demo-run/review', '分镜审查'],
    ['/batches', '批量队列'],
    ['/artifacts', '产物库'],
    ['/recovery', '故障恢复'],
  ])('renders %s', async (path, heading) => {
    renderRoute(path)

    expect(
      await screen.findByRole('heading', { name: heading }),
    ).toBeInTheDocument()
  })
})
