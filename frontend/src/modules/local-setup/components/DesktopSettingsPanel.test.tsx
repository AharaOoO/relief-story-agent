import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { DesktopSettingsPanel } from './DesktopSettingsPanel'

const desktopState = {
  platform: 'win32',
  shell: 'electron',
  isDev: true,
  settingsPath: 'C:/Users/me/AppData/Roaming/Relief Story Agent/settings.json',
  backendUrl: 'http://127.0.0.1:8891',
  frontendDevUrl: 'http://127.0.0.1:5173/',
  uiOrigin: 'http://127.0.0.1:5173',
  backendRunning: true,
  backendPid: 1234,
  settings: {
    host: '127.0.0.1',
    backendPort: 8891,
    frontendPort: 5173,
    comfyUiEndpoint: 'http://127.0.0.1:8188',
    workflowPath: 'D:/ComfyUI/workflows/ltx23_four_grid.json',
    stateDir: 'D:/relief/state',
    logDir: 'D:/relief/logs',
  },
}

describe('DesktopSettingsPanel', () => {
  beforeEach(() => {
    delete window.reliefDesktop
  })

  it('saves edited ports and restarts the local backend from the desktop bridge', async () => {
    const save = vi.fn().mockImplementation(async (settings) => ({
      ...desktopState,
      backendUrl: `http://${settings.host}:${settings.backendPort}`,
      settings,
    }))
    const restart = vi.fn().mockResolvedValue({
      ...desktopState,
      backendUrl: 'http://127.0.0.1:8899',
      settings: {
        ...desktopState.settings,
        backendPort: 8899,
      },
    })
    window.reliefDesktop = {
      platform: 'win32',
      shell: 'electron',
      settings: {
        load: vi.fn().mockResolvedValue(desktopState),
        save,
        reset: vi.fn(),
      },
      backend: {
        restart,
        status: vi.fn().mockResolvedValue(desktopState),
      },
      logs: {
        open: vi.fn(),
      },
    }

    render(<DesktopSettingsPanel />)

    expect(await screen.findByDisplayValue('8891')).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('后端端口'), {
      target: { value: '8899' },
    })
    fireEvent.change(screen.getByLabelText('ComfyUI 地址'), {
      target: { value: 'http://127.0.0.1:8199' },
    })
    fireEvent.click(
      screen.getByRole('button', { name: /保存并重启本地服务/ }),
    )

    await waitFor(() => {
      expect(save).toHaveBeenCalledWith(
        expect.objectContaining({
          backendPort: 8899,
          comfyUiEndpoint: 'http://127.0.0.1:8199',
        }),
      )
      expect(restart).toHaveBeenCalled()
    })
    expect(screen.getByText(/配置已保存/)).toBeInTheDocument()
    expect(screen.getByText('http://127.0.0.1:8899')).toBeInTheDocument()
  })

  it('keeps the settings readable when the Electron bridge is unavailable', () => {
    render(<DesktopSettingsPanel />)

    expect(screen.getByText('桌面客户端功能不可用')).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /保存并重启本地服务/ }),
    ).toBeDisabled()
  })
})
