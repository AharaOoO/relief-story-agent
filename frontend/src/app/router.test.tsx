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

describe('workbench router', () => {
  it.each([
    ['/', '把一个想法，交给整条制片流水线'],
    ['/autopilot', '自动执行'],
    ['/run/demo-run', '自动执行'],
    ['/tasks', '任务队列'],
    ['/assets', '资产库'],
  ])('renders %s in the new workbench', async (path, heading) => {
    renderRoute(path)

    expect(
      await screen.findByRole('heading', { name: heading }),
    ).toBeInTheDocument()
    expect(screen.queryByText('LTX 2.3 Studio Console')).not.toBeInTheDocument()
  })
})
