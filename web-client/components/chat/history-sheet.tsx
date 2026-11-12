"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import * as DropdownMenu from "@radix-ui/react-dropdown-menu"
import { MoreHorizontal, Pencil, Trash2 } from "lucide-react"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { deleteThread, listThreads, renameThread } from "@/lib/chat-api"
import type { ThreadSummary } from "@/lib/types"
import { displayTitle } from "@/lib/thread-title"
import { cn } from "@/lib/utils"

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
  activeId: string | null
  /** Bumped when the transcript changes (e.g. a new thread was titled) so an open list refreshes. */
  refreshKey: number
  onSelect: (id: string) => void
  onDeleted: (id: string) => void
}

export function HistorySheet({ open, onOpenChange, activeId, refreshKey, onSelect, onDeleted }: Props) {
  const [threads, setThreads] = useState<ThreadSummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [editing, setEditing] = useState<string | null>(null)
  const [draft, setDraft] = useState("")

  const editRef = useRef<HTMLInputElement>(null)

  // Focus the rename field once the dropdown menu has finished closing (it would otherwise take focus back).
  useEffect(() => {
    if (!editing) return
    const t = setTimeout(() => {
      editRef.current?.focus()
      editRef.current?.select()
    }, 50)
    return () => clearTimeout(t)
  }, [editing])

  const load = useCallback(async () => {
    try {
      const { threads } = await listThreads()
      setThreads(threads)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load conversations")
      setThreads((t) => t ?? [])
    }
  }, [])

  useEffect(() => {
    if (!open) {
      setEditing(null)
      return
    }
    setThreads(null)
    void load()
  }, [open, refreshKey, load])

  const commitRename = async (id: string) => {
    const title = draft.trim()
    setEditing(null)
    if (!title) return
    try {
      await renameThread(id, title)
      setThreads((ts) => ts?.map((t) => (t.id === id ? { ...t, title } : t)) ?? ts)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Rename failed")
    }
  }

  const remove = async (id: string) => {
    try {
      await deleteThread(id)
      setThreads((ts) => ts?.filter((t) => t.id !== id) ?? ts)
      onDeleted(id)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Delete failed")
    }
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent>
        <SheetHeader>
          <SheetTitle>History</SheetTitle>
          <SheetDescription>Your recent conversations on this device.</SheetDescription>
        </SheetHeader>
        {error && (
          <p className="text-sm text-destructive" role="alert">
            {error}
          </p>
        )}
        <div className="-mx-2 flex-1 space-y-1 overflow-y-auto px-2">
          {threads === null &&
            [0, 1, 2, 3].map((i) => (
              <div key={i} data-testid="history-skeleton" className="h-12 animate-pulse rounded-md bg-muted" />
            ))}
          {threads?.length === 0 && !error && (
            <p className="py-6 text-center text-sm text-muted-foreground">No conversations yet.</p>
          )}
          {threads?.map((t) => (
            <div
              key={t.id}
              className={cn(
                "group flex items-center gap-1 rounded-md pr-1 hover:bg-accent",
                t.id === activeId && "bg-accent"
              )}
            >
              {editing === t.id ? (
                <form
                  className="flex-1 p-1"
                  onSubmit={(e) => {
                    e.preventDefault()
                    void commitRename(t.id)
                  }}
                >
                  <Input
                    ref={editRef}
                    value={draft}
                    maxLength={200}
                    aria-label="Conversation title"
                    onChange={(e) => setDraft(e.target.value)}
                    onBlur={() => void commitRename(t.id)}
                    onKeyDown={(e) => e.key === "Escape" && setEditing(null)}
                    className="h-8"
                  />
                </form>
              ) : (
                <button
                  type="button"
                  className="min-w-0 flex-1 px-3 py-2 text-left"
                  onClick={() => onSelect(t.id)}
                >
                  <div className={cn("truncate text-sm font-medium", !t.title && "italic text-muted-foreground")}>
                    {displayTitle(t.title)}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {new Date(t.last_activity_at).toLocaleString()}
                  </div>
                </button>
              )}
              <DropdownMenu.Root>
                <DropdownMenu.Trigger asChild>
                  <Button variant="ghost" size="icon" className="h-8 w-8 shrink-0" aria-label={`Options for ${displayTitle(t.title)}`}>
                    <MoreHorizontal className="h-4 w-4" />
                  </Button>
                </DropdownMenu.Trigger>
                <DropdownMenu.Portal>
                  <DropdownMenu.Content
                    align="end"
                    onCloseAutoFocus={(e) => e.preventDefault()}
                    className="z-[60] min-w-[8rem] rounded-md border bg-popover p-1 text-popover-foreground shadow-md"
                  >
                    <DropdownMenu.Item
                      className="flex cursor-pointer items-center gap-2 rounded-sm px-2 py-1.5 text-sm outline-none focus:bg-accent"
                      onSelect={() => {
                        setDraft(t.title ?? "")
                        setEditing(t.id)
                      }}
                    >
                      <Pencil className="h-4 w-4" /> Rename
                    </DropdownMenu.Item>
                    <DropdownMenu.Item
                      className="flex cursor-pointer items-center gap-2 rounded-sm px-2 py-1.5 text-sm text-destructive outline-none focus:bg-accent"
                      onSelect={() => void remove(t.id)}
                    >
                      <Trash2 className="h-4 w-4" /> Delete
                    </DropdownMenu.Item>
                  </DropdownMenu.Content>
                </DropdownMenu.Portal>
              </DropdownMenu.Root>
            </div>
          ))}
        </div>
      </SheetContent>
    </Sheet>
  )
}
