/// <reference types="node" />

import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const css = readFileSync(resolve(process.cwd(), 'src/index.css'), 'utf8')

describe('visual system tokens', () => {
  it('uses the refined Moblinks-inspired console theme instead of the old toy UI tokens', () => {
    expect(css).toContain('--surface-cream: #fff2df;')
    expect(css).toContain('--ink-navy: #203d6f;')
    expect(css).toContain('--accent-gold: #ffc400;')
    expect(css).toContain('--radius-card: 18px;')

    expect(css).not.toContain('--radius-card: 24px;')
    expect(css).not.toContain('radial-gradient(circle at 18% 12%')
    expect(css).not.toContain('.mobile-menu')
  })
})
