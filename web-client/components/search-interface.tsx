"use client"

import { useState } from "react"
import { Search, Loader2, ExternalLink } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { api, ApiError } from "@/lib/api"
import type { QuestionResponse } from "@/lib/types"

export function SearchInterface() {
  const [question, setQuestion] = useState("")
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<QuestionResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleSearch = async () => {
    if (!question.trim()) return

    setLoading(true)
    setError(null)
    setResult(null)

    try {
      const response = await api.askQuestion({ question: question.trim() })
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
            Get evidence-based answers from BC Cancer&apos;s medical resources
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex gap-2">
            <Input
              placeholder="e.g., What are the symptoms of breast cancer?"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyPress={handleKeyPress}
              disabled={loading}
              className="flex-1"
            />
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
                <p className="text-foreground whitespace-pre-wrap">{result.answer}</p>
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
                          <h4 className="font-medium text-sm">{source.article_title}</h4>
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
