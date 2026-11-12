import { ApiError } from "./api"
import { getOwnerKey } from "./owner"
import { parseSSE } from "./sse"
import type {
  ChatCitation,
  ChatMessage,
  ThreadDetail,
  ThreadSettings,
  ThreadSummary,
} from "./types"

const BASE = "/api/v1"

function headers(json = false): Record<string, string> {
  const h: Record<string, string> = { "X-Owner-Key": getOwnerKey() }
  if (json) h["Content-Type"] = "application/json"
  return h
}

async function errorFrom(response: Response): Promise<ApiError> {
  const body = await response.json().catch(() => null)
  return new ApiError(
    body?.message || body?.detail || `HTTP ${response.status}`,
    response.status,
    body
  )
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${BASE}${path}`, init)
  if (!response.ok) throw await errorFrom(response)
  return response.json()
}

export function listThreads(): Promise<{ threads: ThreadSummary[] }> {
  return request("/threads", { headers: headers() })
}

export function getThread(id: string): Promise<ThreadDetail> {
  return request(`/threads/${encodeURIComponent(id)}`, { headers: headers() })
}

export function renameThread(id: string, title: string): Promise<{ id: string; title: string }> {
  return request(`/threads/${encodeURIComponent(id)}`, {
    method: "PATCH",
    headers: headers(true),
    body: JSON.stringify({ title }),
  })
}

export function deleteThread(id: string): Promise<{ ok: boolean }> {
  return request(`/threads/${encodeURIComponent(id)}`, {
    method: "DELETE",
    headers: headers(),
  })
}

export function updateThreadSettings(
  id: string,
  settings: ThreadSettings
): Promise<{ settings: ThreadSettings; marker: ChatMessage | null }> {
  return request(`/threads/${encodeURIComponent(id)}/settings`, {
    method: "PATCH",
    headers: headers(true),
    body: JSON.stringify(settings),
  })
}

export interface StreamHandlers {
  onStatus(stage: string, query?: string): void
  onCitations(citations: ChatCitation[]): void
  onToken(text: string): void
  onDone(done: { thread_id: string; message_id: string; disclaimer: string }): void
  onError(message: string): void
}

export async function streamChat(
  req: { threadId: string | null; message: string; settings?: ThreadSettings },
  handlers: StreamHandlers,
  signal?: AbortSignal
): Promise<{ threadId: string; httpStatus?: number }> {
  let threadId = req.threadId ?? ""
  // Exactly one terminal callback (onDone or onError) per call, unless aborted.
  let terminated = false

  // Consumer exceptions must not be mistaken for network failures.
  const safe = (fn: () => void) => {
    try {
      fn()
    } catch (e) {
      console.error("streamChat handler threw", e)
    }
  }
  const fail = (message: string) => {
    if (terminated) return
    terminated = true
    safe(() => handlers.onError(message))
  }
  const dispatch = (event: string, raw: unknown) => {
    if (terminated || !raw || typeof raw !== "object") return
    const data = raw as Record<string, any>
    switch (event) {
      case "status":
        safe(() => handlers.onStatus(data.stage, data.query))
        break
      case "citations":
        safe(() => handlers.onCitations(Array.isArray(data.citations) ? data.citations : []))
        break
      case "token":
        if (typeof data.text === "string") safe(() => handlers.onToken(data.text))
        break
      case "done":
        if (data.thread_id) threadId = data.thread_id
        terminated = true
        safe(() => handlers.onDone(data as any))
        break
      case "error":
        fail(typeof data.message === "string" ? data.message : "Chat failed")
        break
    }
  }

  try {
    const response = await fetch(`${BASE}/chat`, {
      method: "POST",
      headers: headers(true),
      body: JSON.stringify({
        thread_id: req.threadId,
        message: req.message,
        ...(req.settings ? { settings: req.settings } : {}),
      }),
      signal,
    })
    threadId = response.headers.get("X-Thread-Id") ?? threadId

    if (!response.ok || !response.body) {
      fail((await errorFrom(response)).message)
      return response.ok ? { threadId } : { threadId, httpStatus: response.status }
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ""
    for (;;) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const parsed = parseSSE(buffer)
      buffer = parsed.rest
      for (const e of parsed.events) dispatch(e.event, e.data)
    }
    if (!terminated && !signal?.aborted) {
      fail("The response was interrupted before it finished.")
    }
  } catch (e) {
    if ((e as Error)?.name !== "AbortError" && !signal?.aborted) {
      fail(e instanceof Error ? e.message : "Network error")
    }
  }
  return { threadId }
}
