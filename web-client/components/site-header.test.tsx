import { beforeEach, describe, expect, it, vi } from "vitest"
// @ts-ignore -- no @types/react-dom installed
import { renderToStaticMarkup } from "react-dom/server"

let pathname = "/"
vi.mock("next/navigation", () => ({ usePathname: () => pathname }))

import { SiteHeader, isActivePath } from "./site-header"

const render = (path: string) => {
  pathname = path
  const div = document.createElement("div")
  div.innerHTML = renderToStaticMarkup(<SiteHeader />)
  return div
}

describe("isActivePath", () => {
  it("matches the route and pages below it, not look-alike prefixes", () => {
    expect(isActivePath("/chat", "/chat")).toBe(true)
    expect(isActivePath("/chat/abc", "/chat")).toBe(true)
    expect(isActivePath("/chatter", "/chat")).toBe(false)
    expect(isActivePath("/", "/chat")).toBe(false)
    expect(isActivePath(null, "/chat")).toBe(false)
  })
})

describe("SiteHeader", () => {
  beforeEach(() => {
    pathname = "/"
  })

  it("links the logo to the landing page", () => {
    const home = render("/chat").querySelector('a[aria-label="Care Beacon home"]')
    expect(home?.getAttribute("href")).toBe("/")
  })

  it("links the tabs to /chat, /search and /stats in that order", () => {
    const hrefs = [...render("/").querySelectorAll("nav a")].map((a) => a.getAttribute("href"))
    expect(hrefs).toEqual(["/chat", "/search", "/stats"])
  })

  it("marks no tab current on the landing page", () => {
    expect(render("/").querySelectorAll('[aria-current="page"]')).toHaveLength(0)
  })

  it.each([
    ["/chat", "/chat"],
    ["/search", "/search"],
    ["/stats", "/stats"],
  ])("marks only the %s tab current", (path, href) => {
    const current = render(path).querySelectorAll('[aria-current="page"]')
    expect(current).toHaveLength(1)
    expect(current[0].getAttribute("href")).toBe(href)
  })
})
