/// <reference types="node" />

import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const css = readFileSync(resolve(process.cwd(), 'src/index.css'), 'utf8')

describe('visual system tokens', () => {
  it('uses the approved ice coast glass design tokens', () => {
    expect(css).toContain('--coast-bg: #f7f9fc;')
    expect(css).toContain('--coast-ink: #252832;')
    expect(css).toContain('--coast-accent: #6e9fff;')
    expect(css).toContain('--coast-glass: rgba(255, 255, 255, 0.64);')
    expect(css).toContain('--radius-card: 24px;')

    expect(css).not.toContain('--surface-cream: #fff2df;')
    expect(css).not.toContain('--accent-gold: #ffc400;')
    expect(css).not.toContain('font-size: clamp(')
    expect(css).not.toContain('letter-spacing: -')
  })
})
