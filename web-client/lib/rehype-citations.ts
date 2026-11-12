// Dependency-free hast transform: turns "[n]" in text into <cite data-cite="n">[n]</cite>
// when 1 <= n <= count, skipping anything inside <code> or <pre>.

interface HastNode {
  type: string
  value?: string
  tagName?: string
  properties?: Record<string, unknown>
  children?: HastNode[]
}

const MARKER = /\[(\d+)\]/g
const SKIP = new Set(["code", "pre"])

function splitText(value: string, count: number): HastNode[] | null {
  const out: HastNode[] = []
  let last = 0
  let found = false
  for (const m of value.matchAll(MARKER)) {
    const n = Number(m[1])
    if (n < 1 || n > count) continue
    found = true
    const start = m.index ?? 0
    if (start > last) out.push({ type: "text", value: value.slice(last, start) })
    out.push({
      type: "element",
      tagName: "cite",
      properties: { "data-cite": String(n) },
      children: [{ type: "text", value: m[0] }],
    })
    last = start + m[0].length
  }
  if (!found) return null
  if (last < value.length) out.push({ type: "text", value: value.slice(last) })
  return out
}

function walk(node: HastNode, count: number) {
  if (!node.children) return
  if (node.type === "element" && node.tagName && SKIP.has(node.tagName)) return
  const next: HastNode[] = []
  for (const child of node.children) {
    if (child.type === "text" && typeof child.value === "string") {
      next.push(...(splitText(child.value, count) ?? [child]))
    } else {
      walk(child, count)
      next.push(child)
    }
  }
  node.children = next
}

export function rehypeCitations(options: { count: number }) {
  return (tree: HastNode) => {
    walk(tree, options.count)
  }
}
