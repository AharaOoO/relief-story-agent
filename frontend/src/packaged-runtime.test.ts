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
    expect(ocean).not.toContain('src="/beach_bg.mp4"')
  })
})
