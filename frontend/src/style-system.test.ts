/// <reference types="node" />

import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const css = readFileSync(resolve(process.cwd(), 'src/index.css'), 'utf8')

describe('visual system tokens', () => {
  it('uses the approved light salon glass design tokens', () => {
    expect(css).toContain('--coast-bg: #f6f9fe;')
    expect(css).toContain('--coast-ink: #252838;')
    expect(css).toContain('--coast-accent: #9dbdff;')
    expect(css).toContain('--coast-glass: rgba(255, 255, 255, 0.64);')
    expect(css).toContain('--radius-card: 34px;')
    expect(css).toContain('font-family: Inter, "Microsoft YaHei UI", "PingFang SC", sans-serif;')
    expect(css).toContain('font-family: "Instrument Serif", "Songti SC", "SimSun", Georgia, serif;')
    expect(css).toContain('.hero-studio-card')
    expect(css).toContain('.hero-glass-ornaments')
    expect(css).toContain('.coast-hero::after')
    expect(css).toContain('rgba(246,249,254,.98) 92%')
    expect(css).toContain('radial-gradient(circle at 50% 8%, rgba(255,255,255,.98), rgba(255,255,255,.42) 38%, transparent 68%)')

    expect(css).not.toContain('--surface-cream: #fff2df;')
    expect(css).not.toContain('--accent-gold: #ffc400;')
    expect(css).not.toContain('font-size: clamp(')
    expect(css).not.toContain('letter-spacing: -')
  })
})
