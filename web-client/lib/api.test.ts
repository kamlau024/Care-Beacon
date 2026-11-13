import { afterEach, describe, expect, it, vi } from "vitest"
import { RATE_LIMITED_MESSAGE, api } from "./api"

afterEach(() => vi.unstubAllGlobals())

describe("api.askQuestion errors", () => {
  it("shows a friendly message for the firewall's rate-limit 429", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        Response.json(
          { error: { code: "429", message: "Too Many Requests", id: "pdx1::abc" } },
          { status: 429 }
        )
      )
    )
    await expect(api.askQuestion({ question: "What is chemotherapy?" })).rejects.toMatchObject({
      message: RATE_LIMITED_MESSAGE,
      status: 429,
    })
  })

  it("keeps the API's own detail message", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(Response.json({ detail: "Question too short" }, { status: 422 }))
    )
    await expect(api.askQuestion({ question: "hi" })).rejects.toMatchObject({
      message: "Question too short",
      status: 422,
    })
  })
})
