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
): Promise<{ threadId: string }> {
  let threadId = req.threadId ?? ""
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
      const err = await errorFrom(response)
      handlers.onError(err.message)
      return { threadId }
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ""
    const dispatch = (event: string, data: any) => {
      switch (event) {
        case "status":
          handlers.onStatus(data.stage, data.query)
          break
        case "citations":
          handlers.onCitations(data.citations)
          break
        case "token":
          handlers.onToken(data.text)
          break
        case "done":
          if (data.thread_id) threadId = data.thread_id
          handlers.onDone(data)
          break
        case "error":
          handlers.onError(data.message)
          break
      }
    }

    for (;;) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const parsed = parseSSE(buffer)
      buffer = parsed.rest
      for (const e of parsed.events) dispatch(e.event, e.data)
    }
  } catch (e) {
    if ((e as Error)?.name !== "AbortError") {
      handlers.onError(e instanceof Error ? e.message : "Network error")
    }
  }
  return { threadId }
}
