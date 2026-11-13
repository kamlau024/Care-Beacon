import { describe, expect, it } from "vitest"
import { ALL_SOURCES, DEFAULT_SETTINGS, describeSettingsChange, settingsEqual } from "./settings"

describe("settings", () => {
  it("has the configured defaults", () => {
    expect(ALL_SOURCES).toEqual(["BC Cancer", "Canadian Cancer Society", "Cleveland Clinic"])
    expect(DEFAULT_SETTINGS).toEqual({ sources: ALL_SOURCES, min_similarity: 0.5 })
  })

  it("settingsEqual ignores source order", () => {
    expect(
      settingsEqual(
        { sources: ["A", "B"], min_similarity: 0.5 },
        { sources: ["B", "A"], min_similarity: 0.5 }
      )
    ).toBe(true)
  })

  it("settingsEqual false when similarity differs", () => {
    expect(
      settingsEqual(
        { sources: ["A"], min_similarity: 0.5 },
        { sources: ["A"], min_similarity: 0.55 }
      )
    ).toBe(false)
  })

  it("settingsEqual false when sources differ", () => {
    expect(
      settingsEqual(
        { sources: ["A"], min_similarity: 0.5 },
        { sources: ["A", "B"], min_similarity: 0.5 }
      )
    ).toBe(false)
  })

  it("describeSettingsChange shows was-values", () => {
    const d = describeSettingsChange({
      before: { sources: [...ALL_SOURCES], min_similarity: 0.5 },
      after: { sources: ["BC Cancer", "Canadian Cancer Society"], min_similarity: 0.55 },
    })
    expect(d.sources).toBe("BC Cancer, Canadian Cancer Society (was + Cleveland Clinic)")
    expect(d.similarity).toBe("55% (was 50%)")
  })

  it("describeSettingsChange reports unchanged", () => {
    const s = { sources: [...ALL_SOURCES], min_similarity: 0.5 }
    expect(describeSettingsChange({ before: s, after: { ...s } })).toEqual({
      sources: "unchanged",
      similarity: "unchanged",
    })
  })
})
