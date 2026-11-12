import { describe, expect, it } from "vitest"
import { UNTITLED, displayTitle } from "./thread-title"

describe("displayTitle", () => {
  it("returns the title when present", () => {
    expect(displayTitle("Radiation side effects")).toBe("Radiation side effects")
  })
  it("falls back for null, undefined and blank titles", () => {
    expect(displayTitle(null)).toBe(UNTITLED)
    expect(displayTitle(undefined)).toBe(UNTITLED)
    expect(displayTitle("   ")).toBe(UNTITLED)
    expect(UNTITLED).toBe("Untitled conversation")
  })
})
