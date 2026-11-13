"use client"

import { ExternalLink } from "lucide-react"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { SourceBadge } from "@/components/ui/source-badge"
import type { ChatCitation } from "@/lib/types"

function safeHref(url: string | undefined): string | null {
  if (!url) return null
  try {
    const u = new URL(url)
    return u.protocol === "http:" || u.protocol === "https:" ? u.href : null
  } catch {
    return null
  }
}

export function CitationChip({
  n,
  citation,
}: {
  n: number
  citation: ChatCitation | undefined
}) {
  // A marker with no matching citation (shouldn't happen: rehypeCitations bounds by count).
  if (!citation) return <span>[{n}]</span>
  const href = safeHref(citation.url)
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label={`Citation ${n}: ${citation.article_title}`}
          className="mx-0.5 inline-flex h-5 min-w-5 items-center justify-center rounded-full border border-primary/30 bg-primary/10 px-1.5 align-baseline text-[11px] font-semibold leading-none text-primary hover:bg-primary/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          {n}
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-80 space-y-2 text-sm" align="start">
        <div className="font-medium leading-snug">{citation.article_title}</div>
        <div className="flex flex-wrap items-center gap-2">
          <SourceBadge source={citation.source} />
          {citation.section && (
            <span className="text-xs text-muted-foreground">{citation.section}</span>
          )}
        </div>
        <p className="max-h-40 overflow-y-auto text-xs text-muted-foreground">
          {citation.excerpt}
        </p>
        {href && (
          <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
          >
            Open source <ExternalLink className="h-3 w-3" />
          </a>
        )}
      </PopoverContent>
    </Popover>
  )
}
