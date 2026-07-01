import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

describe('packaged desktop runtime', () => {
  it('uses relative assets and hash routing for file URLs', () => {
    const viteConfig = readFileSync(resolve(process.cwd(), 'vite.config.ts'), 'utf8')
    const router = readFileSync(resolve(process.cwd(), 'src/app/router.tsx'), 'utf8')
    const ocean = readFileSync(resolve(process.cwd(), 'src/shared/components/OceanVideoBackground.tsx'), 'utf8')

    expect(viteConfig).toContain("base: './'")
    expect(router).toContain('createHashRouter(routes)')
    expect(router).not.toContain('createBrowserRouter(routes)')
    expect(ocean).toContain('import.meta.env.BASE_URL')
    expect(ocean).toContain('coast-loop.mp4')
    expect(ocean).not.toContain('src="/coast-loop.mp4"')
    expect(ocean).not.toContain('beach_bg.mp4')
    expect(ocean).not.toContain('prefers-reduced-motion')
    expect(ocean).not.toContain('video.pause()')
  })

  it('keeps the ocean hero video crisp without soft-focus transforms', () => {
    const css = readFileSync(resolve(process.cwd(), 'src/index.css'), 'utf8')
    const videoRule = css.match(/\.ocean-video-layer video\s*\{[^}]+\}/s)?.[0] ?? ''

    expect(videoRule).toContain('filter: none')
    expect(videoRule).toContain('transform: none')
    expect(videoRule).not.toContain('blur(')
  })
})
