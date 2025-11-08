"use client"

import { useEffect, useState } from "react"
import { BarChart3, TrendingDown, Zap, Database, Loader2 } from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { api, ApiError } from "@/lib/api"
import type { StatsResponse } from "@/lib/types"

export function StatsDashboard() {
  const [stats, setStats] = useState<StatsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchStats = async () => {
    setLoading(true)
    setError(null)

    try {
      const response = await api.getStats()
      setStats(response)
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message)
      } else {
        setError("Failed to fetch statistics")
      }
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchStats()
  }, [])

  if (loading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center h-48">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </CardContent>
      </Card>
    )
  }

  if (error) {
    return (
      <Card className="border-destructive">
        <CardHeader>
          <CardTitle className="text-destructive">Error Loading Statistics</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">{error}</p>
        </CardContent>
      </Card>
    )
  }

  if (!stats) return null

  return (
    <div className="space-y-4">
      {/* Overview Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Cost */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Cost</CardTitle>
            <BarChart3 className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">${stats.total_cost.toFixed(4)}</div>
            <p className="text-xs text-muted-foreground">
              {stats.llm.total_calls} API calls
            </p>
          </CardContent>
        </Card>

        {/* Cache Hit Rate */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Cache Hit Rate</CardTitle>
            <Zap className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {(stats.cache.hit_rate * 100).toFixed(1)}%
            </div>
            <p className="text-xs text-muted-foreground">
              {stats.cache.cache_hits} / {stats.cache.total_queries} queries
            </p>
          </CardContent>
        </Card>

        {/* Cost Saved */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Cost Saved</CardTitle>
            <TrendingDown className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">${stats.total_cost_saved.toFixed(4)}</div>
            <p className="text-xs text-muted-foreground">
              {stats.cost_reduction_percent.toFixed(1)}% reduction
            </p>
          </CardContent>
        </Card>

        {/* Embeddings */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Embeddings</CardTitle>
            <Database className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.retrieval.total_tokens_used}</div>
            <p className="text-xs text-muted-foreground">
              ${stats.retrieval.total_cost.toFixed(6)} cost
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Detailed Statistics */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* LLM Statistics */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <span>LLM Statistics</span>
              <Badge variant="outline">{stats.llm.model}</Badge>
            </CardTitle>
            <CardDescription>OpenAI API usage metrics</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Total Calls</span>
              <span className="font-medium">{stats.llm.total_calls}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Input Tokens</span>
              <span className="font-medium">{stats.llm.total_input_tokens.toLocaleString()}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Output Tokens</span>
              <span className="font-medium">{stats.llm.total_output_tokens.toLocaleString()}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Total Tokens</span>
              <span className="font-medium">{stats.llm.total_tokens.toLocaleString()}</span>
            </div>
            <div className="flex justify-between text-sm border-t pt-2">
              <span className="text-muted-foreground">Avg Cost/Call</span>
              <span className="font-medium">${stats.llm.avg_cost_per_call.toFixed(6)}</span>
            </div>
          </CardContent>
        </Card>

        {/* Cache Statistics */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <span>Cache Statistics</span>
              <Badge variant={stats.cache.enabled ? "default" : "secondary"}>
                {stats.cache.enabled ? "Enabled" : "Disabled"}
              </Badge>
            </CardTitle>
            <CardDescription>Redis cache performance</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Total Queries</span>
              <span className="font-medium">{stats.cache.total_queries}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Cache Hits</span>
              <span className="font-medium text-green-600 dark:text-green-400">
                {stats.cache.cache_hits}
              </span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Cache Misses</span>
              <span className="font-medium text-orange-600 dark:text-orange-400">
                {stats.cache.cache_misses}
              </span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Hit Rate</span>
              <span className="font-medium">{(stats.cache.hit_rate * 100).toFixed(1)}%</span>
            </div>
            <div className="flex justify-between text-sm border-t pt-2">
              <span className="text-muted-foreground">Time Saved</span>
              <span className="font-medium">
                {stats.cache.total_time_saved_ms.toFixed(0)}ms
              </span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Retrieval Statistics */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span>Vector Database Statistics</span>
            <Badge variant="outline">{stats.retrieval.model}</Badge>
          </CardTitle>
          <CardDescription>Embedding and retrieval metrics</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <p className="text-xs text-muted-foreground">Dimensions</p>
              <p className="text-lg font-semibold">{stats.retrieval.dimensions}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Tokens Used</p>
              <p className="text-lg font-semibold">{stats.retrieval.total_tokens_used}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Total Cost</p>
              <p className="text-lg font-semibold">${stats.retrieval.total_cost.toFixed(6)}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Cost/1k Tokens</p>
              <p className="text-lg font-semibold">${stats.retrieval.cost_per_1k_tokens.toFixed(6)}</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
