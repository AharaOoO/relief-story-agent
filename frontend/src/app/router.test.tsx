import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
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
  beforeEach(() => {
    vi.spyOn(window, 'scrollTo').mockImplementation(() => undefined)
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

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

  it('keeps the dashboard focused on the light glass one-page production entry', async () => {
    renderRoute('/')

    expect(await screen.findByText('自动制片中枢')).toBeInTheDocument()
    expect(screen.getByText('10 道工序')).toBeInTheDocument()
    expect(screen.getByText('海滩灵感工作台')).toBeInTheDocument()
  })

  it('resets scroll to the top when opening the autopilot configuration page', async () => {
    const scrollTo = vi.mocked(window.scrollTo)
    renderRoute('/')

    const configureLink = await screen.findByRole('link', { name: /配置每一道工序/ })
    scrollTo.mockClear()
    fireEvent.click(configureLink)

    expect(await screen.findByRole('heading', { name: /自动执行/ })).toBeInTheDocument()
    await waitFor(() => expect(scrollTo).toHaveBeenCalledWith({ top: 0, left: 0, behavior: 'auto' }))
  })
})
