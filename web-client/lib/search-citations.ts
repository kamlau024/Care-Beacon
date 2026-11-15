import type { ChatCitation, Citation } from "@/lib/types"

/** One piece of a Search answer: plain text, or a citation pointing at result.sources[n - 1]. */
export type AnswerSegment = { type: "text"; text: string } | { type: "cite"; n: number }

// Search answers cite inline as [Source: Article Title - Section] (or without "Source:").
const CITATION_PATTERN = /\[(?:Source:\s*)?([^\]]+?)\s*-\s*([^\]]+?)\]/g

const norm = (s: string) => s.trim().toLowerCase()

/**
 * Index of the source a citation refers to, or -1. Prefers a source whose title and section both match,
 * because one article often appears several times with different sections; falls back to the first
 * source whose title contains (or is contained in) the cited title.
 */
export function findSourceIndex(sources: Citation[], title: string, section: string): number {
  const t = norm(title)
  const s = norm(section)
  const titleMatches = (src: Citation) => {
    const st = norm(src.article_title)
    return st.includes(t) || t.includes(st)
  }
  const exact = sources.findIndex((src) => titleMatches(src) && norm(src.section) === s)
  return exact !== -1 ? exact : sources.findIndex(titleMatches)
}

/**
 * Splits a Search answer into text and numbered citations. A citation's number is its source's position
 * in the Sources list (1-based), so the chip and the Sources card show the same number. A citation that
 * matches no source stays as its original text.
 */
export function segmentAnswer(text: string, sources: Citation[]): AnswerSegment[] {
  const segments: AnswerSegment[] = []
  let lastIndex = 0
  const pushText = (t: string) => {
    if (!t) return
    const prev = segments[segments.length - 1]
    if (prev?.type === "text") prev.text += t
    else segments.push({ type: "text", text: t })
  }

  for (const match of text.matchAll(CITATION_PATTERN)) {
    const index = match.index ?? 0
    pushText(text.slice(lastIndex, index))
    const i = findSourceIndex(sources, match[1], match[2])
    if (i === -1) pushText(match[0])
    else segments.push({ type: "cite", n: i + 1 })
    lastIndex = index + match[0].length
  }
  pushText(text.slice(lastIndex))
  return segments
}

/** Adapts a Search source to the shape the Chat citation chip shows in its popover. */
export function toChatCitation(source: Citation, n: number): ChatCitation {
  return {
    n,
    article_title: source.article_title,
    section: source.section,
    url: source.url,
    source: source.source,
    similarity_score: source.similarity_score,
    excerpt: source.text_excerpt,
  }
}
