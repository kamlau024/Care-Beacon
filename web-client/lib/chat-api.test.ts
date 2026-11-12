import { afterEach, describe, expect, it, vi } from "vitest"
import { deleteThread, getThread, listThreads, streamChat, updateThreadSettings } from "./chat-api"

const handlers = () => ({
  onStatus: vi.fn(),
  onCitations: vi.fn(),
  onToken: vi.fn(),
  onDone: vi.fn(),
  onError: vi.fn(),
})

function sseResponse(chunks: string[], headers: Record<string, string> = {}) {
  const enc = new TextEncoder()
  const body = new ReadableStream({
    start(c) {
      chunks.forEach((ch) => c.enqueue(enc.encode(ch)))
      c.close()
    },
  })
  return new Response(body, {
    status: 200,
    headers: { "Content-Type": "text/event-stream", ...headers },
  })
}

afterEach(() => {
  vi.unstubAllGlobals()
  localStorage.clear()
})

describe("streamChat", () => {
  it("streamChat surfaces the 429 message", async () => {
    const msg = "Today's chat limit has been reached. It resets at midnight UTC."
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ error: "DailyLimitReached", message: msg }), {
          status: 429,
          headers: { "Content-Type": "application/json" },
        })
      )
    )
    const h = handlers()
    await streamChat({ threadId: null, message: "hello there" }, h)
    expect(h.onError).toHaveBeenCalledWith(msg)
    expect(h.onToken).not.toHaveBeenCalled()
  })

  it("sends owner header and thread_id, dispatches events across split chunks", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      sseResponse(
        [
          'event: status\ndata: {"stage":"searching","query":"q"}\n\nevent: tok',
          'en\ndata: {"text":"Hi"}\n\nevent: citations\ndata: {"citations":[]}\n\n',
          'event: done\ndata: {"thread_id":"t1","message_id":"m1","disclaimer":"d"}\n\n',
        ],
        { "X-Thread-Id": "t1" }
      )
    )
    vi.stubGlobal("fetch", fetchMock)
    const h = handlers()
    const res = await streamChat(
      { threadId: "t0", message: "hello there", settings: { sources: ["A"], min_similarity: 0.5 } },
      h
    )
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe("/api/v1/chat")
    expect(init.headers["X-Owner-Key"]).toMatch(/^[0-9a-f-]{36}$/)
    expect(JSON.parse(init.body)).toEqual({
      thread_id: "t0",
      message: "hello there",
      settings: { sources: ["A"], min_similarity: 0.5 },
    })
    expect(h.onStatus).toHaveBeenCalledWith("searching", "q")
    expect(h.onToken).toHaveBeenCalledWith("Hi")
    expect(h.onCitations).toHaveBeenCalledWith([])
    expect(h.onDone).toHaveBeenCalledWith({ thread_id: "t1", message_id: "m1", disclaimer: "d" })
    expect(res).toEqual({ threadId: "t1" })
  })

  it("routes error events and non-OK errors to onError", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(sseResponse(['event: error\ndata: {"message":"boom"}\n\n']))
    )
    const h = handlers()
    await streamChat({ threadId: null, message: "hello there" }, h)
    expect(h.onError).toHaveBeenCalledWith("boom")
  })
})

describe("streamChat terminal callbacks", () => {
  const run = async (resp: Response | Promise<Response>, signal?: AbortSignal, h = handlers()) => {
    vi.stubGlobal("fetch", vi.fn().mockReturnValue(resp))
    await streamChat({ threadId: null, message: "hello there" }, h, signal)
    return h
  }

  it("calls onError exactly once when the stream ends without done", async () => {
    const h = await run(sseResponse(['event: token\ndata: {"text":"a"}\n\n']))
    expect(h.onError).toHaveBeenCalledTimes(1)
    expect(h.onDone).not.toHaveBeenCalled()
  })

  it("ignores done after an error frame", async () => {
    const h = await run(
      sseResponse([
        'event: error\ndata: {"message":"x"}\n\n',
        'event: done\ndata: {"thread_id":"t","message_id":"m","disclaimer":"d"}\n\n',
      ])
    )
    expect(h.onError).toHaveBeenCalledTimes(1)
    expect(h.onDone).not.toHaveBeenCalled()
  })

  it("fires no callback on abort", async () => {
    const ac = new AbortController()
    ac.abort()
    const h = await run(Promise.reject(new DOMException("aborted", "AbortError")), ac.signal)
    expect(h.onError).not.toHaveBeenCalled()
    expect(h.onDone).not.toHaveBeenCalled()
  })

  it("does not throw on a frame whose data is null", async () => {
    const h = await run(
      sseResponse([
        "event: status\ndata: null\n\n",
        'event: done\ndata: {"thread_id":"t","message_id":"m","disclaimer":"d"}\n\n',
      ])
    )
    expect(h.onStatus).not.toHaveBeenCalled()
    expect(h.onError).not.toHaveBeenCalled()
    expect(h.onDone).toHaveBeenCalledTimes(1)
  })

  it("a throwing onToken does not trigger onError", async () => {
    const h = handlers()
    h.onToken.mockImplementation(() => {
      throw new Error("consumer bug")
    })
    vi.spyOn(console, "error").mockImplementation(() => {})
    await run(
      sseResponse([
        'event: token\ndata: {"text":"a"}\n\n',
        'event: done\ndata: {"thread_id":"t","message_id":"m","disclaimer":"d"}\n\n',
      ]),
      undefined,
      h
    )
    expect(h.onError).not.toHaveBeenCalled()
    expect(h.onDone).toHaveBeenCalledTimes(1)
    vi.restoreAllMocks()
  })

  it("non-429 non-2xx response calls onError once", async () => {
    const h = await run(Response.json({ error: "x", message: "db down" }, { status: 503 }))
    expect(h.onError).toHaveBeenCalledTimes(1)
    expect(h.onError).toHaveBeenCalledWith("db down")
  })
})

describe("thread calls", () => {
  it("send X-Owner-Key and parse JSON", async () => {
    const fetchMock = vi.fn().mockImplementation(async () => Response.json({ threads: [], ok: true }))
    vi.stubGlobal("fetch", fetchMock)
    await listThreads()
    await getThread("a")
    await deleteThread("a")
    await updateThreadSettings("a", { sources: [], min_similarity: 0.5 })
    expect(fetchMock.mock.calls.map((c) => [c[0], c[1].method ?? "GET"])).toEqual([
      ["/api/v1/threads", "GET"],
      ["/api/v1/threads/a", "GET"],
      ["/api/v1/threads/a", "DELETE"],
      ["/api/v1/threads/a/settings", "PATCH"],
    ])
    for (const c of fetchMock.mock.calls) expect(c[1].headers["X-Owner-Key"]).toBeTruthy()
  })

  it("throws ApiError with the server message", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(Response.json({ error: "NotFound", message: "nope" }, { status: 404 }))
    )
    await expect(getThread("x")).rejects.toMatchObject({ status: 404, message: "nope" })
  })
})
