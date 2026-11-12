import { describe, expect, it } from "vitest"
import { parseSSE } from "./sse"

describe("parseSSE", () => {
  it("parses multiple frames in one chunk", () => {
    const { events, rest } = parseSSE(
      'event: token\ndata: {"text":"a"}\n\nevent: token\ndata: {"text":"b"}\n\n'
    )
    expect(events).toEqual([
      { event: "token", data: { text: "a" } },
      { event: "token", data: { text: "b" } },
    ])
    expect(rest).toBe("")
  })

  it("parseSSE handles a frame split across two chunks", () => {
    const first = parseSSE('event: token\ndata: {"te')
    expect(first.events).toEqual([])
    const second = parseSSE(first.rest + 'xt":"hi"}\n\n')
    expect(second.events).toEqual([{ event: "token", data: { text: "hi" } }])
    expect(second.rest).toBe("")
  })

  it("keeps a trailing incomplete frame as rest", () => {
    const { events, rest } = parseSSE('event: a\ndata: {"x":1}\n\nevent: b\ndata: {')
    expect(events).toHaveLength(1)
    expect(rest).toBe("event: b\ndata: {")
  })

  it("handles CRLF line endings, including a split CRLF delimiter", () => {
    const a = parseSSE('event: token\r\ndata: {"text":"x"}\r\n\r\n')
    expect(a.events).toEqual([{ event: "token", data: { text: "x" } }])
    const b = parseSSE('event: token\r\ndata: {"text":"y"}\r\n\r')
    expect(b.events).toEqual([])
    const c = parseSSE(b.rest + "\n")
    expect(c.events).toEqual([{ event: "token", data: { text: "y" } }])
  })

  it("skips comments and malformed json", () => {
    const { events } = parseSSE(': ping\n\nevent: x\ndata: not-json\n\nevent: y\ndata: 1\n\n')
    expect(events).toEqual([{ event: "y", data: 1 }])
  })
})
