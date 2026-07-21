import { useRef, useEffect, useState, createElement, useMemo, useCallback, memo } from 'react'

interface Font { fontFamily: string; fontWeight?: number; fontSize?: number | string }
interface Phase { mode?: 'particle' | 'opacity'; order?: 'together' | 'left-to-right' | 'right-to-left'
  transition?: { duration?: number; ease?: string | number[]; delay?: number } }
interface Props {
  texts?: string[]; font?: Font; color?: string; spread?: number; density?: number
  appear?: Phase; disappear?: Phase; alignment?: 'left' | 'center' | 'right'
  tag?: 'h1' | 'h2' | 'h3' | 'p' | 'div' | 'span'
}

function useInView(ref: any, margin = '50px') {
  const [inView, setInView] = useState(false)
  useEffect(() => {
    const el = ref.current
    if (!el || typeof IntersectionObserver === 'undefined') return
    const io = new IntersectionObserver(([e]) => setInView(e.isIntersecting), { rootMargin: margin })
    io.observe(el); return () => io.disconnect()
  }, [ref, margin])
  return inView
}

const TAGS = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'div', 'span'] as const
const NAMED: Record<string, [number, number, number, number]> = {
  linear: [0, 0, 1, 1], easeIn: [0.42, 0, 1, 1], easeOut: [0, 0, 0.58, 1], easeInOut: [0.42, 0, 0.58, 1],
}
function cubic(x1: number, y1: number, x2: number, y2: number) {
  const cx = 3 * x1, bx = 3 * (x2 - x1) - cx, ax = 1 - cx - bx
  const cy = 3 * y1, by = 3 * (y2 - y1) - cy, ay = 1 - cy - by
  const sx = (t: number) => ((ax * t + bx) * t + cx) * t
  const sy = (t: number) => ((ay * t + by) * t + cy) * t
  const dx = (t: number) => (3 * ax * t + 2 * bx) * t + cx
  return (p: number) => {
    let t = p
    for (let i = 0; i < 8; i++) {
      const x = sx(t) - p, d = dx(t)
      if (Math.abs(x) < 1e-4 || Math.abs(d) < 1e-6) break
      t -= x / d
    }
    return sy(t < 0 ? 0 : t > 1 ? 1 : t)
  }
}
const makeEase = (e: any) => Array.isArray(e) && e.length === 4
  ? cubic(e[0], e[1], e[2], e[3])
  : cubic(...((typeof e === 'string' && NAMED[e]) || NAMED.easeOut))
const durOf = (t: any, f: number) => typeof t?.duration === 'number' ? t.duration : f
const delayOf = (t: any, f: number) => typeof t?.delay === 'number' ? t.delay : f
const DRIFT_REACH = 45, SWEEP_SPAN = 0.6

const spreadFor = (fs: any) => {
  const s = typeof fs === 'string' ? parseInt(fs) : fs
  const pts = [{ s: 20, v: 0.2 }, { s: 50, v: 0.5 }, { s: 100, v: 1.5 }]
  if (s <= pts[0].s) return pts[0].v
  if (s >= pts[2].s) return pts[2].v
  let i = 0; while (i < pts.length - 1 && pts[i + 1].s < s) i++
  const a = pts[i], b = pts[i + 1]
  return a.v + ((s - a.s) * (b.v - a.v)) / (b.s - a.s)
}
const localProgress = (e: number, start = 0) => {
  const span = 1 - start
  if (span <= 0) return e >= start ? 1 : 0
  return Math.max(0, Math.min(1, (e - start) / span))
}
const assignStarts = (ps: any[], b: any, order: string) => {
  const w = b?.width || 1, l = b?.left ?? 0
  for (const p of ps) {
    if (order === 'together') { p.start = 0; continue }
    const f = Math.max(0, Math.min(1, (p.originalX - l) / w))
    p.start = (order === 'right-to-left' ? 1 - f : f) * SWEEP_SPAN
  }
}
const assignScatter = (ps: any[], spread: number) => {
  const reach = Math.max(20, spread * 60)
  for (const p of ps) {
    const a = Math.random() * Math.PI * 2, d = (0.4 + Math.random() * 0.6) * reach
    p.scatterX = p.originalX + Math.cos(a) * d
    p.scatterY = p.originalY + Math.sin(a) * d * 0.5
  }
}
const resetParticles = (ps: any[]) => ps.forEach(p => {
  p.x = p.originalX; p.y = p.originalY; p.opacity = p.originalAlpha
  p.speed = 0; p.driftX = 0; p.driftY = 0
})
const updateParticles = (ps: any[], prog: number, spread: number, density: number) => {
  for (const p of ps) {
    if (prog < (p.start ?? 0)) continue
    if (p.speed === 0) {
      p.angle = Math.random() * Math.PI * 2
      p.speed = 0.5 + Math.random()
      const reach = p.speed * spread * DRIFT_REACH
      p.driftX = Math.cos(p.angle) * reach
      p.driftY = Math.sin(p.angle) * reach * 0.6
      p.wobble = (Math.random() - 0.5) * 2
      p.fadeFast = Math.random() > density
    }
    const l = localProgress(prog, p.start ?? 0)
    p.opacity = p.originalAlpha * (1 - (p.fadeFast ? Math.min(1, l * 2) : l))
    const travel = l * (2 - l)
    const wob = Math.sin(l * Math.PI * 3 + p.angle) * p.wobble * spread * 4 * l
    p.x = p.originalX + p.driftX * travel + wob
    p.y = p.originalY + p.driftY * travel
  }
}
const renderParticles = (ctx: any, ps: any[], dpr: number, bufRef: any, canvas: any) => {
  const w = canvas.width, h = canvas.height
  if (w <= 0 || h <= 0) return
  let buf = bufRef.current
  if (!buf || buf.width !== w || buf.height !== h) { buf = ctx.createImageData(w, h); bufRef.current = buf }
  const data = buf.data; data.fill(0)
  const size = Math.max(1, canvas.particleSize || Math.round(dpr))
  for (const p of ps) {
    if (p.opacity <= 0.01) continue
    const alpha = p.opacity > 1 ? 255 : (p.opacity * 255) | 0
    const px = p.x | 0, py = p.y | 0
    for (let dy = 0; dy < size; dy++) {
      const y = py + dy
      if (y < 0 || y >= h) continue
      let idx = (y * w + px) * 4
      for (let dx = 0; dx < size; dx++) {
        const x = px + dx
        if (x >= 0 && x < w) { data[idx] = p.r; data[idx + 1] = p.g; data[idx + 2] = p.b; data[idx + 3] = alpha }
        idx += 4
      }
    }
  }
  ctx.putImageData(buf, 0, 0)
}
const createParticles = (ctx: any, canvas: any, text: string, tx: number, ty: number,
  font: string, color: string, alignment: string) => {
  const particles: any[] = []
  ctx.clearRect(0, 0, canvas.width, canvas.height)
  ctx.fillStyle = color; ctx.font = font; ctx.textAlign = alignment; ctx.textBaseline = 'middle'
  ctx.imageSmoothingQuality = 'high'; ctx.imageSmoothingEnabled = true
  const m = ctx.measureText(text), tw = m.width
  const left = alignment === 'center' ? tx - tw / 2 : alignment === 'left' ? tx : tx - tw
  ctx.fillText(text, tx, ty)
  const asc = m.actualBoundingBoxAscent || 60, desc = m.actualBoundingBoxDescent || 20, pad = 4
  const x0 = Math.max(0, Math.floor(left - pad)), y0 = Math.max(0, Math.floor(ty - asc - pad))
  const x1 = Math.min(canvas.width, Math.ceil(left + tw + pad)), y1 = Math.min(canvas.height, Math.ceil(ty + desc + pad))
  const bw = Math.max(1, x1 - x0), bh = Math.max(1, y1 - y0)
  const data = ctx.getImageData(x0, y0, bw, bh).data
  const dpr = canvas.width / parseInt(canvas.style.width)
  const rate = Math.max(1, Math.round(dpr))
  canvas.particleSize = rate
  for (let y = 0; y < bh; y += rate) for (let x = 0; x < bw; x += rate) {
    const i = (y * bw + x) * 4, a = data[i + 3]
    if (a > 0) particles.push({
      x: x0 + x, y: y0 + y, originalX: x0 + x, originalY: y0 + y,
      r: data[i], g: data[i + 1], b: data[i + 2],
      opacity: a / 255, originalAlpha: a / 255,
      angle: 0, speed: 0, start: 0, driftX: 0, driftY: 0, wobble: 0,
      scatterX: 0, scatterY: 0, fadeFast: false,
    })
  }
  ctx.clearRect(0, 0, canvas.width, canvas.height)
  return { particles, textBoundaries: { left, right: left + tw, width: tw } }
}

const Seo = memo(({ tag = 'p', texts }: any) => createElement(
  (TAGS as readonly string[]).includes(tag) ? tag : 'p',
  { style: { position: 'absolute', width: 0, height: 0, overflow: 'hidden', pointerEvents: 'none' } },
  texts?.join(' ') ?? ''))
Seo.displayName = 'Seo'

export default function VaporizeText(props: Props = {}) {
  const texts = props.texts ?? ['TRUTHGUARD']
  const font = props.font ?? { fontFamily: 'Instrument Serif', fontWeight: 400, fontSize: 120 }
  const color = props.color ?? 'rgb(255,255,255)'
  const spread = props.spread ?? 12
  const density = props.density ?? 10
  const appear = props.appear ?? { mode: 'particle', order: 'left-to-right', transition: { duration: 1.2, ease: 'easeOut' } }
  const disappear = props.disappear ?? { mode: 'particle', order: 'left-to-right', transition: { duration: 2, ease: 'easeOut', delay: 2.2 } }
  const alignment = props.alignment ?? 'center'
  const tag = props.tag ?? 'h1'

  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const wrapperRef = useRef<HTMLDivElement | null>(null)
  const inView = useInView(wrapperRef)
  const particlesRef = useRef<any[]>([])
  const bufferRef = useRef<ImageData | null>(null)
  const phaseRef = useRef<'out' | 'in' | 'hold'>('in')
  const phaseTimeRef = useRef(0)
  const scatterRef = useRef<any>(null)
  const startsRef = useRef<any>(null)
  const startsKeyRef = useRef('')
  const holdDrawnRef = useRef(false)
  const [idx, setIdx] = useState(0)
  const [size, setSize] = useState<{ width: number | null; height: number | null }>({ width: null, height: null })

  const dpr = useMemo(() => typeof window === 'undefined' ? 1 : Math.min(2, window.devicePixelRatio || 1), [])
  const density01 = Math.min(1, Math.max(0.3, 0.3 + (density / 10) * 0.7))

  const timing = useMemo(() => ({
    outMode: disappear.mode ?? 'particle', outOrder: disappear.order ?? 'left-to-right',
    outDuration: Math.max(0.01, durOf(disappear.transition, 2)), outEase: makeEase(disappear.transition?.ease),
    inMode: appear.mode ?? 'particle', inOrder: appear.order ?? 'together',
    inDuration: Math.max(0.01, durOf(appear.transition, 1)), inEase: makeEase(appear.transition?.ease),
    hold: Math.max(0, delayOf(disappear.transition, 0.5)),
  }), [JSON.stringify(disappear), JSON.stringify(appear)])

  const fontSize = parseInt(String(font.fontSize ?? 120).replace('px', ''))
  const multSpread = spreadFor(fontSize) * spread

  const draw = useCallback((ctx: any, ps: any, canvas: any) =>
    renderParticles(ctx, ps, dpr, bufferRef, canvas), [dpr])

  useEffect(() => {
    const el = wrapperRef.current
    if (!el || typeof ResizeObserver === 'undefined') return
    const ro = new ResizeObserver(e => {
      const r = e[0]?.contentRect; if (!r) return
      const w = Math.round(r.width), h = Math.round(r.height)
      setSize(p => p.width === w && p.height === h ? p : { width: w, height: h })
    })
    ro.observe(el); return () => ro.disconnect()
  }, [])

  // build particles when text / size changes
  useEffect(() => {
    const canvas = canvasRef.current as any
    if (!canvas || !size.width || !size.height) return
    const ctx = canvas.getContext('2d'); if (!ctx) return
    const f = `${font.fontWeight ?? 400} ${fontSize * dpr}px ${font.fontFamily}`
    const text = texts[idx] || 'TRUTHGUARD'
    ctx.font = f
    const widest = texts.reduce((w: number, t: string) => Math.max(w, ctx.measureText(t || '').width), 0)
    const overflowX = Math.max(0, (widest / dpr - size.width) / 2)
    const driftRoom = spreadFor(fontSize) * spread * DRIFT_REACH * 0.6
    const bleed = Math.ceil(Math.min(400, overflowX + fontSize + driftRoom))
    const cssW = size.width + bleed * 2, cssH = size.height + bleed * 2
    canvas.style.width = `${cssW}px`; canvas.style.height = `${cssH}px`
    canvas.style.left = `${-bleed}px`; canvas.style.top = `${-bleed}px`
    canvas.width = Math.floor(cssW * dpr); canvas.height = Math.floor(cssH * dpr)
    const inset = bleed * dpr, boxW = size.width * dpr
    const tx = alignment === 'center' ? inset + boxW / 2 : alignment === 'left' ? inset : inset + boxW
    const { particles, textBoundaries } = createParticles(ctx, canvas, text, tx, canvas.height / 2, f, color, alignment)
    particlesRef.current = particles
    canvas.textBoundaries = textBoundaries
  }, [JSON.stringify(texts), idx, size.width, size.height, fontSize, font.fontFamily, font.fontWeight, color, alignment, spread, dpr])

  useEffect(() => {
    if (!inView) return
    let last = performance.now(), raf = 0
    const tick = (now: number) => {
      const dt = Math.min((now - last) / 1000, 0.1); last = now
      const canvas = canvasRef.current as any
      const ctx = canvas?.getContext('2d')
      const ps = particlesRef.current
      if (!canvas || !ctx || !ps.length) { raf = requestAnimationFrame(tick); return }
      const t = timing
      phaseTimeRef.current += dt
      if (phaseRef.current === 'out') {
        const p = Math.min(1, phaseTimeRef.current / t.outDuration), e = t.outEase(p)
        if (startsRef.current !== ps || startsKeyRef.current !== `out|${t.outOrder}`) {
          assignStarts(ps, canvas.textBoundaries, t.outOrder); startsRef.current = ps; startsKeyRef.current = `out|${t.outOrder}`
        }
        if (t.outMode === 'particle') updateParticles(ps, e, multSpread, density01)
        else for (const q of ps) { q.x = q.originalX; q.y = q.originalY; q.opacity = q.originalAlpha * (1 - localProgress(e, q.start)) }
        draw(ctx, ps, canvas)
        if (p >= 1) {
          setIdx(v => (v + 1) % Math.max(1, texts.length))
          phaseRef.current = 'in'; phaseTimeRef.current = 0
          scatterRef.current = null; startsRef.current = null; startsKeyRef.current = ''
        }
      } else if (phaseRef.current === 'in') {
        const p = Math.min(1, phaseTimeRef.current / t.inDuration), e = t.inEase(p)
        if (startsRef.current !== ps || startsKeyRef.current !== `in|${t.inOrder}`) {
          assignStarts(ps, canvas.textBoundaries, t.inOrder); startsRef.current = ps; startsKeyRef.current = `in|${t.inOrder}`
        }
        if (t.inMode === 'particle') {
          if (scatterRef.current !== ps) { assignScatter(ps, multSpread); scatterRef.current = ps }
          for (const q of ps) {
            const l = localProgress(e, q.start)
            q.x = q.scatterX + (q.originalX - q.scatterX) * l
            q.y = q.scatterY + (q.originalY - q.scatterY) * l
            q.opacity = q.originalAlpha * l
          }
        } else for (const q of ps) { q.x = q.originalX; q.y = q.originalY; q.opacity = q.originalAlpha * localProgress(e, q.start) }
        draw(ctx, ps, canvas)
        if (p >= 1) { resetParticles(ps); phaseRef.current = 'hold'; phaseTimeRef.current = 0; startsKeyRef.current = '' }
      } else {
        if (!holdDrawnRef.current) { draw(ctx, ps, canvas); holdDrawnRef.current = true }
        if (phaseTimeRef.current >= t.hold) {
          resetParticles(ps); phaseRef.current = 'out'; phaseTimeRef.current = 0
          startsKeyRef.current = ''; holdDrawnRef.current = false
        }
      }
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [inView, draw, timing, multSpread, density01, texts.length])

  return (
    <div ref={wrapperRef} style={{ width: '100%', height: '100%', position: 'relative', pointerEvents: 'none', overflow: 'visible' }}>
      <canvas ref={canvasRef} style={{ position: 'absolute', pointerEvents: 'none' }} />
      <Seo tag={tag} texts={texts} />
    </div>
  )
}
