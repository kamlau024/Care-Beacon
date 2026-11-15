import { describe, expect, it, vi } from "vitest"
// @ts-ignore -- no @types/react-dom installed
import { renderToStaticMarkup } from "react-dom/server"

vi.mock("next/navigation", () => ({ usePathname: () => "/" }))

import { GITHUB_URL, LandingPage, SOURCES } from "./landing-page"

const render = () => {
  const div = document.createElement("div")
  div.innerHTML = renderToStaticMarkup(<LandingPage />)
  return div
}

describe("LandingPage", () => {
  it("has one h1, the hero headline", () => {
    const h1s = render().querySelectorAll("h1")
    expect(h1s).toHaveLength(1)
    expect(h1s[0].textContent).toContain("trace to the source")
  })

  it("sends the hero buttons to Chat and Search", () => {
    const page = render()
    const start = [...page.querySelectorAll("a")].find((a) => a.textContent?.includes("Start a chat"))
    const search = [...page.querySelectorAll("a")].find((a) => a.textContent === "Search the library")
    expect(start?.getAttribute("href")).toBe("/chat")
    expect(search?.getAttribute("href")).toBe("/search")
  })

  it("links each of the three sources to its site in a new tab", () => {
    const page = render()
    expect(SOURCES.map((s) => s.name)).toEqual(["BC Cancer", "Canadian Cancer Society", "Cleveland Clinic"])
    for (const source of SOURCES) {
      const link = page.querySelector(`a[href="${source.url}"]`)
      expect(link?.textContent).toBe(source.name)
      expect(link?.getAttribute("target")).toBe("_blank")
      expect(link?.getAttribute("rel")).toBe("noopener noreferrer")
    }
  })

  it("shows the medical disclaimer, short and long", () => {
    const text = render().textContent ?? ""
    expect(text).toContain("For educational purposes only. Consult healthcare professionals for medical advice.")
    expect(text).toContain("is not medical advice")
    expect(text).toContain("not for emergencies")
  })

  it("links to the GitHub repository", () => {
    expect(render().querySelector(`a[href="${GITHUB_URL}"]`)?.textContent).toBe("Source on GitHub")
  })
})
