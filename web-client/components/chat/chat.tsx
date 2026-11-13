"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { History, Plus, Send, SlidersHorizontal } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { getThread, streamChat, updateThreadSettings } from "@/lib/chat-api"
import { MAX_MESSAGE_LENGTH, MIN_MESSAGE_LENGTH, restoreInputAfter, showCounter, tooShort } from "@/lib/chat-input"
import { DEFAULT_SETTINGS, settingsEqual } from "@/lib/settings"
import type { ThreadSettings } from "@/lib/types"
import { HistorySheet } from "./history-sheet"
import { SettingsPanel } from "./settings-panel"
import { Transcript, type DisplayMessage } from "./transcript"

let localCounter = 0
const localId = (prefix: string) => `local-${prefix}-${++localCounter}`

export function Chat() {
  const [threadId, setThreadId] = useState<string | null>(null)
  const [messages, setMessages] = useState<DisplayMessage[]>([])
  const [settings, setSettings] = useState<ThreadSettings>(DEFAULT_SETTINGS)
  const [disclaimer, setDisclaimer] = useState<string | null>(null)
  const [input, setInput] = useState("")
  const [streaming, setStreaming] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const [historyOpen, setHistoryOpen] = useState(false)
  const [historyKey, setHistoryKey] = useState(0)
  const [panelOpen, setPanelOpen] = useState(false)

  const abortRef = useRef<AbortController | null>(null)
  const runRef = useRef(0) // identifies the current stream/load; stale callbacks are ignored
  const baselineRef = useRef<ThreadSettings>(DEFAULT_SETTINGS)
  const threadIdRef = useRef<string | null>(null)
  threadIdRef.current = threadId

  // Cancel any in-flight stream on unmount.
  useEffect(() => () => abortRef.current?.abort(), [])

  const cancelRun = useCallback(() => {
    runRef.current++
    abortRef.current?.abort()
    abortRef.current = null
    setStreaming(false)
  }, [])

  const newChat = useCallback(() => {
    cancelRun()
    setThreadId(null)
    setMessages([])
    setSettings(DEFAULT_SETTINGS)
    setDisclaimer(null)
    setNotice(null)
    setInput("")
    setHistoryOpen(false)
  }, [cancelRun])

  const openThread = useCallback(
    async (id: string) => {
      cancelRun()
      const run = runRef.current
      setHistoryOpen(false)
      setNotice(null)
      try {
        const t = await getThread(id)
        if (runRef.current !== run) return
        setThreadId(t.id)
        setSettings(t.settings)
        setMessages(t.messages)
        setDisclaimer(null)
      } catch (e) {
        if (runRef.current !== run) return
        setNotice(e instanceof Error ? e.message : "Could not open conversation")
      }
    },
    [cancelRun]
  )

  const send = async () => {
    const text = input.trim()
    if (!text || streaming || tooShort(text)) return
    setInput("")
    setNotice(null)
    setDisclaimer(null)

    const pendingId = localId("a")
    const now = new Date().toISOString()
    const base = { thread_id: threadId ?? "", tokens: 0, cost: 0, created_at: now }
    setMessages((m) => [
      ...m,
      { ...base, id: localId("u"), role: "user", content: text, citations: null, settings_delta: null, status: "complete" },
      {
        ...base,
        id: pendingId,
        role: "assistant",
        content: "",
        citations: null,
        settings_delta: null,
        status: "complete",
        pending: true,
        stage: null,
      },
    ])

    const run = ++runRef.current
    const controller = new AbortController()
    abortRef.current = controller
    setStreaming(true)
    const patch = (p: Partial<DisplayMessage> | ((m: DisplayMessage) => Partial<DisplayMessage>)) => {
      if (runRef.current !== run) return
      setMessages((ms) =>
        ms.map((m) => (m.id === pendingId ? { ...m, ...(typeof p === "function" ? p(m) : p) } : m))
      )
    }

    const { threadId: tid, httpStatus } = await streamChat(
      { threadId, message: text, ...(threadId ? {} : { settings }) },
      {
        onStatus: (stage) => patch({ stage }),
        onCitations: (citations) => patch({ citations }),
        onToken: (t) => patch((m) => ({ content: m.content + t })),
        onDone: (done) => {
          if (runRef.current !== run) return
          patch({ id: done.message_id, pending: false, stage: null })
          setThreadId(done.thread_id)
          setDisclaimer(done.disclaimer || null)
          setHistoryKey((k) => k + 1)
        },
        onError: (message) => patch({ pending: false, stage: null, error: message }),
      },
      controller.signal
    )
    if (runRef.current !== run) return
    // Even a failed first turn may have created the thread; keep follow-ups attached to it.
    if (tid) setThreadId(tid)
    // A rejected request (e.g. 422, 429) shouldn't lose what the user typed.
    if (restoreInputAfter(httpStatus)) setInput((cur) => cur || text)
    abortRef.current = null
    setStreaming(false)
    setHistoryKey((k) => k + 1)
  }

  const onPanelOpenChange = async (open: boolean) => {
    setPanelOpen(open)
    if (open) {
      baselineRef.current = settings
      return
    }
    const before = baselineRef.current
    const after = settings
    // Commit only on close, and only if something actually changed.
    if (settingsEqual(before, after)) return
    if (!threadId) return // no thread yet: kept locally, sent with the first message
    // The click that dismissed the popover may also switch thread / start a new chat. Drop the
    // result if either changed; the server-side write for the original thread is still correct.
    const tid = threadId
    const run = runRef.current
    const stale = () => runRef.current !== run || threadIdRef.current !== tid
    try {
      const res = await updateThreadSettings(tid, after)
      if (stale()) return
      setSettings(res.settings)
      if (res.marker) setMessages((m) => [...m, res.marker!])
    } catch (e) {
      if (stale()) return
      setSettings(before)
      setNotice(e instanceof Error ? e.message : "Could not save retrieval settings")
    }
  }

  return (
    <div className="flex h-[calc(100dvh-14rem)] min-h-[440px] flex-col">
      <div className="flex items-center justify-between gap-2 border-b pb-3">
        <Button variant="outline" size="sm" onClick={() => setHistoryOpen(true)}>
          <History /> History
        </Button>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={newChat}>
            <Plus /> New chat
          </Button>
          <Popover open={panelOpen} onOpenChange={onPanelOpenChange}>
            <PopoverTrigger asChild>
              <Button variant="outline" size="sm" disabled={streaming} aria-label="Retrieval settings">
                <SlidersHorizontal /> <span>Retrieval</span>
              </Button>
            </PopoverTrigger>
            <PopoverContent align="end" className="w-80">
              <SettingsPanel settings={settings} onChange={setSettings} />
            </PopoverContent>
          </Popover>
        </div>
      </div>

      <Transcript messages={messages} disclaimer={disclaimer} />

      {notice && (
        <p className="pb-2 text-sm text-destructive" role="alert">
          {notice}
        </p>
      )}

      {(tooShort(input) || showCounter(input.length)) && (
        <p className="flex justify-between pb-1 text-xs text-muted-foreground" aria-live="polite">
          <span>{tooShort(input) ? `Questions need at least ${MIN_MESSAGE_LENGTH} characters.` : ""}</span>
          <span>{showCounter(input.length) ? `${input.length}/${MAX_MESSAGE_LENGTH}` : ""}</span>
        </p>
      )}

      <form
        className="flex items-end gap-2 border-t pt-3"
        onSubmit={(e) => {
          e.preventDefault()
          void send()
        }}
      >
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault()
              void send()
            }
          }}
          rows={1}
          maxLength={MAX_MESSAGE_LENGTH}
          disabled={streaming}
          placeholder="Ask a question…"
          aria-label="Your question"
          className="h-10 flex-1 resize-none rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
        />
        <Button type="submit" disabled={streaming || !input.trim() || tooShort(input)} aria-label="Send">
          <Send />
        </Button>
      </form>

      <HistorySheet
        open={historyOpen}
        onOpenChange={setHistoryOpen}
        activeId={threadId}
        refreshKey={historyKey}
        onSelect={(id) => void openThread(id)}
        onDeleted={(id) => id === threadId && newChat()}
      />
    </div>
  )
}
