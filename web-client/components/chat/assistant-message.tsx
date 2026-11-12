"use client"

import { memo, useMemo } from "react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { Loader2 } from "lucide-react"
import { rehypeCitations } from "@/lib/rehype-citations"
import type { ChatCitation } from "@/lib/types"
import { CitationChip } from "./citation-chip"

const STAGE_TEXT: Record<string, string> = {
  rewriting: "Rewriting your question…",
  searching: "Searching sources…",
  ranking: "Ranking sources…",
}

interface Props {
  content: string
  citations: ChatCitation[] | null
  pending?: boolean
  stage?: string | null
  error?: string | null
  interrupted?: boolean
}

export const AssistantMessage = memo(function AssistantMessage({
  content,
  citations,
  pending,
  stage,
  error,
  interrupted,
}: Props) {
  const count = citations?.length ?? 0
  const byN = useMemo(() => new Map((citations ?? []).map((c) => [c.n, c])), [citations])
  const rehypePlugins = useMemo(() => [[rehypeCitations, { count }] as any], [count])
  const components = useMemo(
    () => ({
      cite: ({ node, children, ...props }: any) => {
        const n = Number(props["data-cite"])
        return Number.isFinite(n) ? <CitationChip n={n} citation={byN.get(n)} /> : <cite>{children}</cite>
      },
      a: ({ node, ...props }: any) => <a {...props} target="_blank" rel="noopener noreferrer" />,
    }),
    [byN]
  )

  return (
    <div className="space-y-2">
      {content && (
        <div className="prose prose-sm dark:prose-invert max-w-none break-words [&_table]:block [&_table]:overflow-x-auto [&_pre]:overflow-x-auto">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            rehypePlugins={rehypePlugins}
            components={components}
          >
            {content}
          </ReactMarkdown>
        </div>
      )}
      {pending && !content && !error && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground" role="status">
          <Loader2 className="h-4 w-4 animate-spin" />
          {STAGE_TEXT[stage ?? ""] ?? "Thinking…"}
        </div>
      )}
      {error && (
        <p className="text-sm text-destructive" role="alert">
          {error}
        </p>
      )}
      {interrupted && <p className="text-xs italic text-muted-foreground">Response interrupted</p>}
    </div>
  )
})
