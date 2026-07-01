/// <reference types="node" />

import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const css = readFileSync(resolve(process.cwd(), 'src/index.css'), 'utf8')

describe('visual system tokens', () => {
  it('uses the approved light salon glass design tokens', () => {
    expect(css).toContain('--coast-bg: #f9fbff;')
    expect(css).toContain('--coast-ink: #202231;')
    expect(css).toContain('--coast-accent: #8fb6ff;')
    expect(css).toContain('--coast-glass: rgba(255, 255, 255, 0.58);')
    expect(css).toContain('--radius-card: 30px;')
    expect(css).toContain('font-family: Inter, "Microsoft YaHei UI", "PingFang SC", sans-serif;')
    expect(css).toContain('font-family: "Instrument Serif", "Songti SC", "SimSun", Georgia, serif;')
    expect(css).toContain('.hero-studio-card')
    expect(css).toContain('.coast-hero::after')
    expect(css).toContain('rgba(249,251,255,.96) 96%')

    expect(css).not.toContain('--surface-cream: #fff2df;')
    expect(css).not.toContain('--accent-gold: #ffc400;')
    expect(css).not.toContain('font-size: clamp(')
    expect(css).not.toContain('letter-spacing: -')
  })
})
