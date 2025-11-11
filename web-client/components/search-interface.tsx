"use client"

import React, { useState } from "react"
import { Search, Loader2, ExternalLink, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Checkbox } from "@/components/ui/checkbox"
import { Slider } from "@/components/ui/slider"
import { api, ApiError } from "@/lib/api"
import type { QuestionResponse, Citation } from "@/lib/types"

interface SearchInterfaceProps {
  question: string
  setQuestion: (value: string) => void
  loading: boolean
  setLoading: (value: boolean) => void
  result: QuestionResponse | null
  setResult: (value: QuestionResponse | null) => void
  error: string | null
  setError: (value: string | null) => void
}

const SOURCES = [
  { id: "bc-cancer", label: "BC Cancer" },
  { id: "canadian-cancer-society", label: "Canadian Cancer Society" },
]

// Helper function to parse and linkify citations in the answer
function parseCitations(text: string, sources: Citation[]): React.ReactNode[] {
  // Pattern to match citations like [Source: Article Title - Section] or [Article Title - Section]
  const citationPattern = /\[(?:Source:\s*)?([^\]]+?)\s*-\s*([^\]]+?)\]/g

  const parts: React.ReactNode[] = []
  let lastIndex = 0
  let match: RegExpExecArray | null

  while ((match = citationPattern.exec(text)) !== null) {
    // Add text before the citation
    if (match.index > lastIndex) {
      parts.push(text.substring(lastIndex, match.index))
    }

    const fullMatch = match[0]
    const articleTitle = match[1].trim()
    const section = match[2].trim()

    // Try to find matching source
    const matchingSource = sources.find(
      source =>
        source.article_title.toLowerCase().includes(articleTitle.toLowerCase()) ||
        articleTitle.toLowerCase().includes(source.article_title.toLowerCase())
    )

    if (matchingSource) {
      // Create clickable link
      parts.push(
        <a
          key={`citation-${match.index}`}
          href={matchingSource.url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline inline-flex items-center gap-1"
        >
          {fullMatch}
          <ExternalLink className="h-3 w-3" />
        </a>
      )
    } else {
      // No matching source, render as plain text
      parts.push(fullMatch)
    }

    lastIndex = match.index + fullMatch.length
  }

  // Add remaining text
  if (lastIndex < text.length) {
    parts.push(text.substring(lastIndex))
  }

  return parts.length > 0 ? parts : [text]
}

// Helper function to get badge styling based on source
function getSourceBadgeStyle(source: string): string {
  if (source === "BC Cancer") {
    // Blue/cyan theme matching the image
    return "bg-blue-100 text-blue-700 border-blue-200 dark:bg-blue-900/30 dark:text-blue-400 dark:border-blue-800"
  } else if (source === "Canadian Cancer Society") {
    // Green/lime theme matching the image
    return "bg-green-100 text-green-700 border-green-200 dark:bg-green-900/30 dark:text-green-400 dark:border-green-800"
  }
  // Default fallback
  return "bg-gray-100 text-gray-700 border-gray-200 dark:bg-gray-900/30 dark:text-gray-400 dark:border-gray-800"
}

export function SearchInterface({
  question,
  setQuestion,
  loading,
  setLoading,
  result,
  setResult,
  error,
  setError,
}: SearchInterfaceProps) {
  // Source filter state - both sources selected by default
  const [selectedSources, setSelectedSources] = useState<string[]>([
    "BC Cancer",
    "Canadian Cancer Society",
  ])

  // Minimum similarity score state - default to 0.5 (50%)
  const [minSimilarity, setMinSimilarity] = useState<number>(0.5)

  const handleSourceToggle = (sourceLabel: string) => {
    setSelectedSources((prev) => {
      // If this is the only source selected, don't allow unchecking it
      if (prev.length === 1 && prev.includes(sourceLabel)) {
        return prev
      }

      // Toggle the source
      if (prev.includes(sourceLabel)) {
        return prev.filter((s) => s !== sourceLabel)
      } else {
        return [...prev, sourceLabel]
      }
    })
  }

  const handleSearch = async () => {
    if (!question.trim()) return

    setLoading(true)
    setError(null)
    setResult(null)

    try {
      // Build request with source filter and min similarity
      const requestData: any = { question: question.trim() }

      // If only one source is selected, add it as a filter
      if (selectedSources.length === 1) {
        requestData.source = selectedSources[0]
      }
      // If both sources are selected, don't add source filter (search all)

      // Add minimum similarity threshold
      if (minSimilarity > 0) {
        requestData.min_similarity = minSimilarity
      }

      const response = await api.askQuestion(requestData)
      setResult(response)
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message)
      } else {
        setError("An unexpected error occurred")
      }
    } finally {
      setLoading(false)
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      handleSearch()
    }
  }

  return (
    <div className="space-y-6">
      {/* Search Input */}
      <Card>
        <CardHeader>
          <CardTitle>Ask a Medical Question</CardTitle>
          <CardDescription>
            Get evidence-based answers from trusted medical resources
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Input
                placeholder="e.g., What are the symptoms of breast cancer?"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyPress={handleKeyPress}
                disabled={loading}
                className="pr-10"
              />
              {question && (
                <button
                  onClick={() => setQuestion("")}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                  type="button"
                  aria-label="Clear input"
                >
                  <X className="h-4 w-4" />
                </button>
              )}
            </div>
          </div>

          {/* Source Filter Checkboxes */}
          <div className="pt-4 space-y-2">
            <div className="text-sm font-medium text-muted-foreground">
              Search in:
            </div>
            <div className="flex flex-wrap gap-4">
              {SOURCES.map((source) => (
                <div key={source.id} className="flex items-center space-x-2">
                  <Checkbox
                    id={source.id}
                    checked={selectedSources.includes(source.label)}
                    onCheckedChange={() => handleSourceToggle(source.label)}
                    disabled={
                      loading ||
                      (selectedSources.length === 1 &&
                        selectedSources.includes(source.label))
                    }
                  />
                  <label
                    htmlFor={source.id}
                    className={`text-sm cursor-pointer ${
                      loading ||
                      (selectedSources.length === 1 &&
                        selectedSources.includes(source.label))
                        ? "opacity-50 cursor-not-allowed"
                        : ""
                    }`}
                  >
                    {source.label}
                  </label>
                </div>
              ))}
            </div>
          </div>

          {/* Minimum Similarity Score Slider */}
          <div className="pt-4 space-y-2">
            <div className="flex items-center justify-between">
              <div className="text-sm font-medium text-muted-foreground">
                Minimum similarity score:
              </div>
              <div className="text-sm font-medium text-foreground">
                {(minSimilarity * 100).toFixed(0)}%
              </div>
            </div>
            <Slider
              value={[minSimilarity]}
              onValueChange={(values) => setMinSimilarity(values[0])}
              min={0}
              max={1}
              step={0.05}
              disabled={loading}
              className="w-full"
            />
            <div className="text-xs text-muted-foreground">
              Only sources with at least this similarity score will be used. Lower values return more sources.
            </div>
          </div>

          <div className="flex gap-2 pt-4">
            <Button onClick={handleSearch} disabled={loading || !question.trim()}>
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Searching...
                </>
              ) : (
                <>
                  <Search className="mr-2 h-4 w-4" />
                  Search
                </>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Error Display */}
      {error && (
        <Card className="border-destructive">
          <CardHeader>
            <CardTitle className="text-destructive">Error</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">{error}</p>
          </CardContent>
        </Card>
      )}

      {/* Results Display */}
      {result && (
        <div className="space-y-4">
          {/* Answer Card */}
          <Card>
            <CardHeader>
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <CardTitle className="text-lg">Answer</CardTitle>
                  <CardDescription>{result.question}</CardDescription>
                </div>
                <div className="flex gap-2">
                  {result.metadata.cached && (
                    <Badge variant="secondary">Cached</Badge>
                  )}
                  <Badge variant="outline">{result.model}</Badge>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="prose prose-sm dark:prose-invert max-w-none">
                <p className="text-foreground whitespace-pre-wrap">
                  {parseCitations(result.answer, result.sources)}
                </p>
              </div>

              {result.disclaimer && (
                <div className="rounded-lg bg-muted p-4 text-sm text-muted-foreground">
                  ℹ️ {result.disclaimer}
                </div>
              )}

              {/* Metadata */}
              <div className="flex flex-wrap gap-4 text-xs text-muted-foreground border-t pt-4">
                <div>
                  <span className="font-medium">Tokens:</span> {result.metadata.tokens_used}
                </div>
                <div>
                  <span className="font-medium">Cost:</span> ${result.metadata.cost.toFixed(6)}
                </div>
                <div>
                  <span className="font-medium">Time:</span> {result.metadata.generation_time_ms.toFixed(0)}ms
                </div>
                <div>
                  <span className="font-medium">Sources:</span> {result.metadata.sources_count}
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Sources Card */}
          {result.sources.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Sources</CardTitle>
                <CardDescription>
                  {result.sources.length} reference{result.sources.length !== 1 ? "s" : ""} found
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {result.sources.map((source, index) => (
                    <div
                      key={index}
                      className="rounded-lg border p-4 hover:bg-accent/50 transition-colors"
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex-1 space-y-1">
                          <div className="flex items-center gap-2 flex-wrap">
                            <h4 className="font-medium text-sm">{source.article_title}</h4>
                            <Badge variant="secondary" className="text-xs">
                              {(source.similarity_score * 100).toFixed(0)}%
                            </Badge>
                            <Badge className={`text-xs border ${getSourceBadgeStyle(source.source)}`}>
                              {source.source}
                            </Badge>
                          </div>
                          <p className="text-xs text-muted-foreground">{source.section}</p>
                          {source.text_excerpt && (
                            <p className="text-xs text-muted-foreground italic mt-2">
                              &quot;{source.text_excerpt}&quot;
                            </p>
                          )}
                        </div>
                        <a
                          href={source.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex items-center gap-1 text-xs text-primary hover:underline whitespace-nowrap"
                        >
                          View <ExternalLink className="h-3 w-3" />
                        </a>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  )
}
