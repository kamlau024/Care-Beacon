import type { SettingsDelta, ThreadSettings } from "./types"

export const ALL_SOURCES = ["BC Cancer", "Canadian Cancer Society", "Cleveland Clinic"]

export const DEFAULT_SETTINGS: ThreadSettings = {
  sources: ALL_SOURCES,
  min_similarity: 0.5,
}

export function settingsEqual(a: ThreadSettings, b: ThreadSettings): boolean {
  if (a.min_similarity !== b.min_similarity) return false
  const sa = new Set(a.sources)
  const sb = new Set(b.sources)
  if (sa.size !== sb.size) return false
  for (const s of sa) if (!sb.has(s)) return false
  return true
}

const pct = (n: number) => `${Math.round(n * 100)}%`

export function describeSettingsChange(delta: SettingsDelta): {
  sources: string
  similarity: string
} {
  const { before, after } = delta

  let sources = "unchanged"
  const beforeSet = new Set(before.sources)
  const afterSet = new Set(after.sources)
  const sameSources =
    beforeSet.size === afterSet.size && [...afterSet].every((s) => beforeSet.has(s))
  if (!sameSources) {
    // "was" shows how to get back to the previous list: removed sources are "+", added are "-".
    const back = [
      ...before.sources.filter((s) => !afterSet.has(s)).map((s) => `+ ${s}`),
      ...after.sources.filter((s) => !beforeSet.has(s)).map((s) => `- ${s}`),
    ]
    sources = `${after.sources.join(", ") || "none"} (was ${back.join(", ")})`
  }

  const similarity =
    before.min_similarity === after.min_similarity
      ? "unchanged"
      : `${pct(after.min_similarity)} (was ${pct(before.min_similarity)})`

  return { sources, similarity }
}
