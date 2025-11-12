"use client"

import { useState, useEffect } from "react"
import { Database, RefreshCw, Loader2 } from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { api, ApiError } from "@/lib/api"
import type { VectorDBStats } from "@/lib/types"

export function VectorDBDisplay() {
  const [stats, setStats] = useState<VectorDBStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)

  const loadStats = async () => {
    setRefreshing(true)
    setError(null)

    try {
      const data = await api.getVectorDBStats()
      setStats(data)
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message)
      } else {
        setError("Failed to load vector database statistics")
      }
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  useEffect(() => {
    loadStats()
  }, [])

  const formatNumber = (num: number) => {
    return num.toLocaleString()
  }

  const getSourceBadgeColor = (source: string) => {
    if (source === "BC Cancer") {
      return "bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200 border-blue-200 dark:border-blue-800"
    } else if (source === "Canadian Cancer Society") {
      return "bg-purple-100 dark:bg-purple-900 text-purple-800 dark:text-purple-200 border-purple-200 dark:border-purple-800"
    }
    return ""
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Database className="h-5 w-5 text-blue-600 dark:text-blue-400" />
            <CardTitle>Vector Database</CardTitle>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={loadStats}
            disabled={refreshing}
          >
            {refreshing ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
          </Button>
        </div>
        <CardDescription>
          Current knowledge base statistics
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Loading State */}
        {loading && !stats && (
          <div className="flex items-center justify-center p-8">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        )}

        {/* Error State */}
        {error && (
          <div className="rounded-lg bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 p-3">
            <p className="text-sm text-red-900 dark:text-red-100">
              ❌ {error}
            </p>
          </div>
        )}

        {/* Stats Display */}
        {stats && (
          <>
            {/* Overall Stats */}
            <div className="grid grid-cols-2 gap-4">
              <div className="rounded-lg border p-4">
                <div className="text-2xl font-bold">{formatNumber(stats.total_documents)}</div>
                <div className="text-xs text-muted-foreground">Total Articles</div>
              </div>
              <div className="rounded-lg border p-4">
                <div className="text-2xl font-bold">{formatNumber(stats.total_chunks)}</div>
                <div className="text-xs text-muted-foreground">Total Chunks</div>
              </div>
            </div>

            {/* Source Breakdown */}
            <div className="space-y-3">
              <h4 className="text-sm font-medium">Data Sources</h4>
              {stats.sources.map((source) => (
                <div
                  key={source.name}
                  className="rounded-lg border p-4 space-y-3"
                >
                  <div className="flex items-center justify-between">
                    <Badge
                      variant="outline"
                      className={getSourceBadgeColor(source.name)}
                    >
                      {source.name}
                    </Badge>
                    <div className="text-sm text-muted-foreground">
                      {((source.chunks / stats.total_chunks) * 100).toFixed(1)}% of total
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1">
                      <div className="text-xs text-muted-foreground">Articles</div>
                      <div className="text-lg font-semibold">
                        {formatNumber(source.articles)}
                      </div>
                    </div>
                    <div className="space-y-1">
                      <div className="text-xs text-muted-foreground">Chunks</div>
                      <div className="text-lg font-semibold">
                        {formatNumber(source.chunks)}
                      </div>
                    </div>
                  </div>

                  {/* Average chunks per article */}
                  <div className="text-xs text-muted-foreground">
                    Average: {(source.chunks / source.articles).toFixed(1)} chunks per article
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  )
}
