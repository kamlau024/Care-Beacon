"use client"

import { useEffect, useState } from "react"
import { BarChart3, TrendingDown, Zap, Database, Loader2, RefreshCw } from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { PieChart, Pie, Cell, ResponsiveContainer, Label } from "recharts"
import { api, ApiError } from "@/lib/api"
import type { StatsResponse, VectorDBStats } from "@/lib/types"

export function StatsDashboard() {
  const [stats, setStats] = useState<StatsResponse | null>(null)
  const [vectorStats, setVectorStats] = useState<VectorDBStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [vectorLoading, setVectorLoading] = useState(true)
  const [vectorError, setVectorError] = useState<string | null>(null)
  const [refreshingVector, setRefreshingVector] = useState(false)

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

  const fetchVectorStats = async () => {
    setRefreshingVector(true)
    setVectorError(null)

    try {
      const data = await api.getVectorDBStats()
      setVectorStats(data)
    } catch (err) {
      if (err instanceof ApiError) {
        setVectorError(err.message)
      } else {
        setVectorError("Failed to load vector database statistics")
      }
    } finally {
      setVectorLoading(false)
      setRefreshingVector(false)
    }
  }

  useEffect(() => {
    fetchStats()
    fetchVectorStats()
  }, [])

  const formatNumber = (num: number) => {
    return num.toLocaleString()
  }

  const getSourceColor = (source: string) => {
    if (source === "BC Cancer") {
      return "hsl(217, 91%, 60%)" // Blue
    } else if (source === "Canadian Cancer Society") {
      return "hsl(271, 91%, 65%)" // Purple
    } else if (source === "Cleveland Clinic") {
      return "hsl(142, 76%, 36%)" // Green
    }
    return "hsl(0, 0%, 60%)" // Gray fallback
  }

  const prepareChartData = (type: "articles" | "chunks") => {
    if (!vectorStats) return []

    return vectorStats.sources.map((source) => ({
      name: source.name,
      value: type === "articles" ? source.articles : source.chunks,
      fill: getSourceColor(source.name),
    }))
  }

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
      {/* Vector Database Statistics - Moved to top */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Database className="h-5 w-5 text-blue-600 dark:text-blue-400" />
              <CardTitle>Vector Database Statistics</CardTitle>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={fetchVectorStats}
              disabled={refreshingVector}
            >
              {refreshingVector ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <RefreshCw className="h-4 w-4" />
              )}
            </Button>
          </div>
          <CardDescription>
            Knowledge base content and embedding metrics
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Loading State */}
          {vectorLoading && !vectorStats && (
            <div className="flex items-center justify-center p-8">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          )}

          {/* Error State */}
          {vectorError && (
            <div className="rounded-lg bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 p-3">
              <p className="text-sm text-red-900 dark:text-red-100">
                ❌ {vectorError}
              </p>
            </div>
          )}

          {/* Donut Charts and Stats */}
          {vectorStats && (
            <>
              {/* Donut Charts */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Articles Donut Chart */}
                <div className="flex flex-col items-center">
                  <h4 className="text-sm font-medium mb-4">Articles by Source</h4>
                  <ResponsiveContainer width="100%" height={250}>
                    <PieChart>
                      <Pie
                        data={prepareChartData("articles")}
                        dataKey="value"
                        nameKey="name"
                        cx="50%"
                        cy="50%"
                        innerRadius={60}
                        outerRadius={80}
                        paddingAngle={2}
                      >
                        {prepareChartData("articles").map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.fill} />
                        ))}
                        <Label
                          content={({ viewBox }) => {
                            if (viewBox && "cx" in viewBox && "cy" in viewBox) {
                              return (
                                <text
                                  x={viewBox.cx}
                                  y={viewBox.cy}
                                  textAnchor="middle"
                                  dominantBaseline="middle"
                                >
                                  <tspan
                                    x={viewBox.cx}
                                    y={(viewBox.cy || 0) - 10}
                                    className="fill-foreground text-3xl font-bold"
                                  >
                                    {formatNumber(vectorStats.total_documents)}
                                  </tspan>
                                  <tspan
                                    x={viewBox.cx}
                                    y={(viewBox.cy || 0) + 15}
                                    className="fill-muted-foreground text-sm"
                                  >
                                    Total Articles
                                  </tspan>
                                </text>
                              )
                            }
                          }}
                        />
                      </Pie>
                    </PieChart>
                  </ResponsiveContainer>
                  {/* Legend */}
                  <div className="mt-4 space-y-2">
                    {vectorStats.sources.map((source) => (
                      <div key={source.name} className="flex items-center gap-2 text-sm">
                        <div
                          className="w-3 h-3 rounded-full"
                          style={{ backgroundColor: getSourceColor(source.name) }}
                        />
                        <span className="text-muted-foreground">
                          {source.name}: {formatNumber(source.articles)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Chunks Donut Chart */}
                <div className="flex flex-col items-center">
                  <h4 className="text-sm font-medium mb-4">Chunks by Source</h4>
                  <ResponsiveContainer width="100%" height={250}>
                    <PieChart>
                      <Pie
                        data={prepareChartData("chunks")}
                        dataKey="value"
                        nameKey="name"
                        cx="50%"
                        cy="50%"
                        innerRadius={60}
                        outerRadius={80}
                        paddingAngle={2}
                      >
                        {prepareChartData("chunks").map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.fill} />
                        ))}
                        <Label
                          content={({ viewBox }) => {
                            if (viewBox && "cx" in viewBox && "cy" in viewBox) {
                              return (
                                <text
                                  x={viewBox.cx}
                                  y={viewBox.cy}
                                  textAnchor="middle"
                                  dominantBaseline="middle"
                                >
                                  <tspan
                                    x={viewBox.cx}
                                    y={(viewBox.cy || 0) - 10}
                                    className="fill-foreground text-3xl font-bold"
                                  >
                                    {formatNumber(vectorStats.total_chunks)}
                                  </tspan>
                                  <tspan
                                    x={viewBox.cx}
                                    y={(viewBox.cy || 0) + 15}
                                    className="fill-muted-foreground text-sm"
                                  >
                                    Total Chunks
                                  </tspan>
                                </text>
                              )
                            }
                          }}
                        />
                      </Pie>
                    </PieChart>
                  </ResponsiveContainer>
                  {/* Legend */}
                  <div className="mt-4 space-y-2">
                    {vectorStats.sources.map((source) => (
                      <div key={source.name} className="flex items-center gap-2 text-sm">
                        <div
                          className="w-3 h-3 rounded-full"
                          style={{ backgroundColor: getSourceColor(source.name) }}
                        />
                        <span className="text-muted-foreground">
                          {source.name}: {formatNumber(source.chunks)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Embedding Metrics */}
              {stats && (
                <div className="border-t pt-4">
                  <h4 className="text-sm font-medium mb-3">Embedding Metrics</h4>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div>
                      <p className="text-xs text-muted-foreground">Model</p>
                      <Badge variant="outline" className="mt-1">{stats.retrieval.model}</Badge>
                    </div>
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
                  </div>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>

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
    </div>
  )
}
