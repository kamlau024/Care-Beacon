import { describe, expect, it } from "vitest"
import { findSourceIndex, segmentAnswer, toChatCitation } from "./search-citations"
import { getCitationNumberStyle } from "./source-colors"
import type { Citation } from "./types"

const src = (article_title: string, section: string, source = "BC Cancer"): Citation => ({
  article_title,
  section,
  source,
  url: `https://example.org/${encodeURIComponent(article_title)}`,
  paragraph_index: 0,
  text_excerpt: `${article_title} excerpt`,
  similarity_score: 0.8,
})

const sources = [
  src("Managing side effects", "Fatigue"),
  src("Managing side effects", "Nausea"),
  src("Chemotherapy", "Overview", "Canadian Cancer Society"),
]

describe("findSourceIndex", () => {
  it("prefers the source whose title and section both match", () => {
    expect(findSourceIndex(sources, "Managing side effects", "Nausea")).toBe(1)
  })
  it("falls back to the first title match when no section matches", () => {
    expect(findSourceIndex(sources, "managing side effects", "Hair loss")).toBe(0)
  })
  it("returns -1 when no title matches", () => {
    expect(findSourceIndex(sources, "Radiation", "Overview")).toBe(-1)
  })
})

describe("segmentAnswer", () => {
  it("numbers citations by their position in the Sources list", () => {
    const text =
      "Tiredness is common [Source: Managing side effects - Fatigue]. Ask about medicine [Chemotherapy - Overview]."
    expect(segmentAnswer(text, sources)).toEqual([
      { type: "text", text: "Tiredness is common " },
      { type: "cite", n: 1 },
      { type: "text", text: ". Ask about medicine " },
      { type: "cite", n: 3 },
      { type: "text", text: "." },
    ])
  })

  it("keeps an unmatched citation as text, merged with its neighbours", () => {
    expect(segmentAnswer("A [Source: Unknown - X] b", sources)).toEqual([
      { type: "text", text: "A [Source: Unknown - X] b" },
    ])
  })

  it("returns the text unchanged when there are no citations", () => {
    expect(segmentAnswer("No citations here.", sources)).toEqual([{ type: "text", text: "No citations here." }])
  })
})

describe("toChatCitation", () => {
  it("maps a Search source to the chip's citation shape", () => {
    expect(toChatCitation(sources[2], 3)).toMatchObject({
      n: 3,
      article_title: "Chemotherapy",
      source: "Canadian Cancer Society",
      excerpt: "Chemotherapy excerpt",
    })
  })
})

describe("getCitationNumberStyle", () => {
  it("colors the chip with its source's badge colors", () => {
    expect(getCitationNumberStyle("BC Cancer")).toContain("bg-blue-100")
    expect(getCitationNumberStyle("Canadian Cancer Society")).toContain("bg-green-100")
    expect(getCitationNumberStyle("Cleveland Clinic")).toContain("bg-orange-100")
    expect(getCitationNumberStyle("Somewhere else")).toContain("bg-gray-100")
  })
})
