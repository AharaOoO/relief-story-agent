import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import AssetsPage from './AssetsPage'
import { listArtifacts } from '../features/workbench/workbench.api'

vi.mock('../features/workbench/workbench.api', () => ({
  listArtifacts: vi.fn().mockResolvedValue([
    {
      id: 'video-one',
      kind: 'video',
      name: 'final.mp4',
      local_path: 'D:/relief/runs/run-one/final.mp4',
    },
    {
      id: 'remote-preview',
      kind: 'image',
      name: 'runninghub-preview.png',
      path: 'https://example.com/preview.png',
    },
  ]),
}))

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={client}>
      <AssetsPage />
    </QueryClientProvider>,
  )
}

describe('AssetsPage', () => {
  const openPath = vi.fn().mockResolvedValue({ opened: true })

  beforeEach(() => {
    vi.clearAllMocks()
    window.reliefDesktop = {
      platform: 'win32',
      shell: 'electron',
      openPath,
    } as unknown as typeof window.reliefDesktop
  })

  it('opens local artifacts and their containing folders from the asset card', async () => {
    renderPage()

    expect(await screen.findByText('final.mp4')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '打开文件 final.mp4' }))
    fireEvent.click(screen.getByRole('button', { name: '打开所在目录 final.mp4' }))

    await waitFor(() => expect(openPath).toHaveBeenCalledWith('D:/relief/runs/run-one/final.mp4'))
    expect(openPath).toHaveBeenCalledWith('D:/relief/runs/run-one')
  })

  it('keeps remote artifact URLs reachable as external links', async () => {
    renderPage()

    const link = await screen.findByRole('link', { name: '打开链接 runninghub-preview.png' })
    expect(link).toHaveAttribute('href', 'https://example.com/preview.png')
    expect(link).toHaveAttribute('target', '_blank')
  })

  it('requests artifacts from the backend library endpoint', async () => {
    renderPage()

    await waitFor(() => expect(listArtifacts).toHaveBeenCalledTimes(1))
  })
})
