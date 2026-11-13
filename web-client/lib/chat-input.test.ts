import { describe, expect, it } from "vitest"
import {
  MAX_MESSAGE_LENGTH,
  MIN_MESSAGE_LENGTH,
  restoreInputAfter,
  showCounter,
  tooShort,
} from "./chat-input"

describe("chat input limits", () => {
  it("matches the server's 3-500 character limits", () => {
    expect(MIN_MESSAGE_LENGTH).toBe(3)
    expect(MAX_MESSAGE_LENGTH).toBe(500)
  })
  it("flags non-empty trimmed text under the minimum", () => {
    expect(tooShort("  hi ")).toBe(true)
    expect(tooShort("hey")).toBe(false)
    expect(tooShort("   ")).toBe(false) // empty: nothing to hint about
  })
  it("shows the counter only near the limit", () => {
    expect(showCounter(0)).toBe(false)
    expect(showCounter(399)).toBe(false)
    expect(showCounter(400)).toBe(true)
    expect(showCounter(500)).toBe(true)
  })
  it("restores typed text after a 4xx rejection only", () => {
    expect(restoreInputAfter(422)).toBe(true)
    expect(restoreInputAfter(429)).toBe(true)
    expect(restoreInputAfter(400)).toBe(true)
    expect(restoreInputAfter(500)).toBe(false)
    expect(restoreInputAfter(undefined)).toBe(false)
  })
})
