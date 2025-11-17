import { getSourceBadgeStyle } from "@/lib/source-colors"

interface SourceBadgeProps {
  source: string
  className?: string
}

export function SourceBadge({ source, className = "" }: SourceBadgeProps) {
  const badgeStyle = getSourceBadgeStyle(source)

  // Debug logging
  if (process.env.NODE_ENV === 'development') {
    console.log('SourceBadge:', { source, sourceLength: source.length, badgeStyle })
  }

  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold ${badgeStyle} ${className}`}
    >
      {source}
    </span>
  )
}
