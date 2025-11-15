"use client"

import { useState, useEffect } from "react"
import { Database, RefreshCw, Loader2 } from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { PieChart, Pie, Cell, ResponsiveContainer, Label } from "recharts"
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

  const getSourceColor = (source: string) => {
    if (source === "BC Cancer") {
      return "hsl(217, 91%, 60%)" // Blue
    } else if (source === "Canadian Cancer Society") {
      return "hsl(271, 91%, 65%)" // Purple
    }
    return "hsl(0, 0%, 60%)" // Gray fallback
  }

  const prepareChartData = (type: "articles" | "chunks") => {
    if (!stats) return []

    return stats.sources.map((source) => ({
      name: source.name,
      value: type === "articles" ? source.articles : source.chunks,
      fill: getSourceColor(source.name),
    }))
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
                                {formatNumber(stats.total_documents)}
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
                {stats.sources.map((source) => (
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
                                {formatNumber(stats.total_chunks)}
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
                {stats.sources.map((source) => (
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
        )}
      </CardContent>
    </Card>
  )
}
