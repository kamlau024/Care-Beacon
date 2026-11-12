"use client"

import { useEffect, useRef } from "react"
import type { ChatCitation, ChatMessage } from "@/lib/types"
import { AssistantMessage } from "./assistant-message"
import { SettingsMarker } from "./settings-marker"

export type DisplayMessage = ChatMessage & {
  pending?: boolean
  stage?: string | null
  error?: string | null
}

export function Transcript({
  messages,
  disclaimer,
}: {
  messages: DisplayMessage[]
  disclaimer: string | null
}) {
  const endRef = useRef<HTMLDivElement>(null)
  const last = messages[messages.length - 1]
  useEffect(() => {
    endRef.current?.scrollIntoView?.({ block: "end" })
  }, [messages.length, last?.content, last?.stage, last?.error])

  if (messages.length === 0) {
    return (
      <div className="flex flex-1 items-center justify-center p-6 text-center text-sm text-muted-foreground">
        Ask a question about cancer care. Answers cite the sources they come from.
      </div>
    )
  }

  return (
    <div className="flex-1 space-y-4 overflow-y-auto overflow-x-hidden px-1 py-4" aria-live="polite">
      {messages.map((m) => {
        if (m.role === "settings") {
          return m.settings_delta ? <SettingsMarker key={m.id} delta={m.settings_delta} /> : null
        }
        if (m.role === "user") {
          return (
            <div key={m.id} className="flex justify-end">
              <div className="max-w-[85%] whitespace-pre-wrap break-words rounded-2xl rounded-br-sm bg-primary px-4 py-2 text-sm text-primary-foreground">
                {m.content}
              </div>
            </div>
          )
        }
        return (
          <div key={m.id} className="flex justify-start">
            <div className="max-w-[95%] rounded-2xl rounded-bl-sm border bg-card px-4 py-3 text-card-foreground">
              <AssistantMessage
                content={m.content}
                citations={m.citations as ChatCitation[] | null}
                pending={m.pending}
                stage={m.stage}
                error={m.error}
                interrupted={m.status === "interrupted"}
              />
            </div>
          </div>
        )
      })}
      {disclaimer && <p className="pt-2 text-center text-xs text-muted-foreground">{disclaimer}</p>}
      <div ref={endRef} />
    </div>
  )
}
