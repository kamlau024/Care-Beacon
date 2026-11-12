import { afterEach, describe, expect, it, vi } from "vitest"

const KEY = "care-beacon-owner-key"

async function load() {
  vi.resetModules()
  return (await import("./owner")).getOwnerKey
}

afterEach(() => {
  vi.unstubAllGlobals()
  localStorage.clear()
})

describe("getOwnerKey", () => {
  it("creates and persists a uuid", async () => {
    const getOwnerKey = await load()
    const k = getOwnerKey()
    expect(k).toMatch(/^[0-9a-f-]{36}$/)
    expect(localStorage.getItem(KEY)).toBe(k)
    expect(getOwnerKey()).toBe(k)
  })

  it("reuses an existing key", async () => {
    localStorage.setItem(KEY, "abc")
    const getOwnerKey = await load()
    expect(getOwnerKey()).toBe("abc")
  })

  it("getOwnerKey falls back when localStorage throws", async () => {
    vi.stubGlobal("localStorage", {
      getItem: () => {
        throw new Error("denied")
      },
      setItem: () => {
        throw new Error("denied")
      },
    })
    const getOwnerKey = await load()
    const k = getOwnerKey()
    expect(k).toMatch(/^[0-9a-f-]{36}$/)
    expect(getOwnerKey()).toBe(k)
  })
})
