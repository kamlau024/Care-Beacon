// Builds every favicon and app icon from the header logo (Lucide's "activity" pulse, ISC
// licence). Run from web-client/:  node scripts/generate-icons.mjs
// Outputs go where Next.js picks them up by file convention (app/) or where the web
// manifest points (public/). Re-run after changing the logo or colours below.

import { writeFile } from "node:fs/promises"
import sharp from "sharp"

// The header logo's path, drawn on a 24×24 grid (spans x 2–22).
const PULSE =
  "M22 12h-2.48a2 2 0 0 0-1.93 1.46l-2.35 8.36a.25.25 0 0 1-.48 0L9.24 2.18a.25.25 0 0 0-.48 0l-2.35 8.36A2 2 0 0 1 4.49 12H2"

// Theme colours from app/globals.css: --foreground (light) 0 0% 3.9%, --background 100%.
const DARK = "#0a0a0a"
const LIGHT = "#ffffff"

/**
 * The pulse on a square tile, on a 32-unit canvas.
 * @param {object} o
 * @param {number} o.radius  corner radius of the tile (0 = full bleed, for iOS and maskable)
 * @param {number} o.inset   space around the pulse, in canvas units
 * @param {number} [o.weight] line thickness, in canvas units
 * @param {boolean} [o.adaptive] add a dark-mode variant (only SVG favicons honour it)
 */
function tile({ radius, inset, weight = 2.6, adaptive = false }) {
  const scale = (32 - 2 * inset) / 20 // the pulse is 20 units wide
  const offset = inset - 2 * scale // move x=2 to the inset
  const style = adaptive
    ? `<style>.t{fill:${DARK}}.p{stroke:${LIGHT}}` +
      `@media (prefers-color-scheme: dark){.t{fill:${LIGHT}}.p{stroke:${DARK}}}</style>`
    : ""
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">${style}
  <rect class="t" width="32" height="32" rx="${radius}" fill="${DARK}"/>
  <path class="p" d="${PULSE}" transform="translate(${offset} ${offset}) scale(${scale})"
    fill="none" stroke="${LIGHT}" stroke-width="${weight / scale}" stroke-linecap="round" stroke-linejoin="round"/>
</svg>
`
}

const rounded = tile({ radius: 7, inset: 5 })
// At 16 px a 2.6-unit line is barely over one pixel; draw it bolder and larger.
const small = tile({ radius: 6, inset: 3.5, weight: 3.6 })
const fullBleed = tile({ radius: 0, inset: 7 }) // iOS rounds the corners itself
const maskable = tile({ radius: 0, inset: 9 }) // pulse stays inside the 80% safe zone

const png = (svg, size) => sharp(Buffer.from(svg), { density: 72 * (size / 32) * 4 }).resize(size, size).png().toBuffer()

/** An .ico holding PNG images (supported by every current browser). */
function ico(images) {
  const header = Buffer.alloc(6 + 16 * images.length)
  header.writeUInt16LE(0, 0) // reserved
  header.writeUInt16LE(1, 2) // type: icon
  header.writeUInt16LE(images.length, 4)
  let offset = header.length
  images.forEach(({ size, data }, i) => {
    const e = 6 + 16 * i
    header.writeUInt8(size >= 256 ? 0 : size, e) // width (0 means 256)
    header.writeUInt8(size >= 256 ? 0 : size, e + 1) // height
    header.writeUInt16LE(1, e + 4) // colour planes
    header.writeUInt16LE(32, e + 6) // bits per pixel
    header.writeUInt32LE(data.length, e + 8)
    header.writeUInt32LE(offset, e + 12)
    offset += data.length
  })
  return Buffer.concat([header, ...images.map((i) => i.data)])
}

const icoSizes = [16, 32, 48]
const icoImages = await Promise.all(
  icoSizes.map(async (size) => ({ size, data: await png(size === 16 ? small : rounded, size) }))
)

await Promise.all([
  writeFile("app/icon.svg", tile({ radius: 7, inset: 5, adaptive: true })),
  writeFile("app/favicon.ico", ico(icoImages)),
  png(fullBleed, 180).then((b) => writeFile("app/apple-icon.png", b)),
  png(rounded, 192).then((b) => writeFile("public/icon-192.png", b)),
  png(rounded, 512).then((b) => writeFile("public/icon-512.png", b)),
  png(maskable, 512).then((b) => writeFile("public/icon-maskable-512.png", b)),
])
console.log("Wrote app/icon.svg, app/favicon.ico, app/apple-icon.png and public/icon-*.png")
