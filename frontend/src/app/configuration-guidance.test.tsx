import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { routes } from './router'

function renderHome() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const router = createMemoryRouter(routes, { initialEntries: ['/'] })
  return render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
}

describe('ordinary-user configuration guidance', () => {
  it('keeps ports and debug configuration out of the primary surface', async () => {
    renderHome()

    expect(
      await screen.findByRole('button', { name: '高级设置' }),
    ).toBeInTheDocument()
    expect(screen.queryByText('http://127.0.0.1:5173')).not.toBeInTheDocument()
    expect(screen.queryByText('http://127.0.0.1:8891')).not.toBeInTheDocument()
  })

  it('opens advanced settings without navigating away', async () => {
    renderHome()

    fireEvent.click(await screen.findByRole('button', { name: '高级设置' }))

    expect(screen.getByRole('dialog', { name: '高级设置' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: '模型与密钥' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'ComfyUI' })).toBeInTheDocument()
  })
})
