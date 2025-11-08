"use client"

import { useState } from "react"
import { Trash2, RotateCcw, AlertTriangle, Loader2 } from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { api, ApiError } from "@/lib/api"

export function AdminControls() {
  const [clearingCache, setClearingCache] = useState(false)
  const [resettingStats, setResettingStats] = useState(false)
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null)

  const handleClearCache = async () => {
    setClearingCache(true)
    setMessage(null)

    try {
      const response = await api.clearCache()
      setMessage({ type: "success", text: response.message })
    } catch (err) {
      if (err instanceof ApiError) {
        setMessage({ type: "error", text: err.message })
      } else {
        setMessage({ type: "error", text: "Failed to clear cache" })
      }
    } finally {
      setClearingCache(false)
    }
  }

  const handleResetStats = async () => {
    setResettingStats(true)
    setMessage(null)

    try {
      const response = await api.resetStats()
      setMessage({ type: "success", text: response.message })
    } catch (err) {
      if (err instanceof ApiError) {
        setMessage({ type: "error", text: err.message })
      } else {
        setMessage({ type: "error", text: "Failed to reset statistics" })
      }
    } finally {
      setResettingStats(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <AlertTriangle className="h-5 w-5 text-orange-600 dark:text-orange-400" />
          Admin Controls
        </CardTitle>
        <CardDescription>
          Manage cache and statistics (use with caution)
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Message Display */}
        {message && (
          <div
            className={`rounded-lg p-3 text-sm ${
              message.type === "success"
                ? "bg-green-50 dark:bg-green-950 text-green-900 dark:text-green-100 border border-green-200 dark:border-green-800"
                : "bg-red-50 dark:bg-red-950 text-red-900 dark:text-red-100 border border-red-200 dark:border-red-800"
            }`}
          >
            {message.text}
          </div>
        )}

        {/* Clear Cache */}
        <div className="flex items-start justify-between gap-4 p-4 rounded-lg border">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-1">
              <h4 className="font-medium text-sm">Clear Cache</h4>
              <Badge variant="outline" className="text-xs">
                Redis
              </Badge>
            </div>
            <p className="text-xs text-muted-foreground">
              Remove all cached query results. Next queries will hit the API and regenerate cache.
            </p>
          </div>
          <Button
            variant="destructive"
            size="sm"
            onClick={handleClearCache}
            disabled={clearingCache}
          >
            {clearingCache ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Clearing...
              </>
            ) : (
              <>
                <Trash2 className="mr-2 h-4 w-4" />
                Clear
              </>
            )}
          </Button>
        </div>

        {/* Reset Statistics */}
        <div className="flex items-start justify-between gap-4 p-4 rounded-lg border">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-1">
              <h4 className="font-medium text-sm">Reset Statistics</h4>
              <Badge variant="outline" className="text-xs">
                Metrics
              </Badge>
            </div>
            <p className="text-xs text-muted-foreground">
              Reset all usage statistics including costs, tokens, and cache metrics to zero.
            </p>
          </div>
          <Button
            variant="destructive"
            size="sm"
            onClick={handleResetStats}
            disabled={resettingStats}
          >
            {resettingStats ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Resetting...
              </>
            ) : (
              <>
                <RotateCcw className="mr-2 h-4 w-4" />
                Reset
              </>
            )}
          </Button>
        </div>

        {/* Warning */}
        <div className="rounded-lg bg-orange-50 dark:bg-orange-950 border border-orange-200 dark:border-orange-800 p-3">
          <p className="text-xs text-orange-900 dark:text-orange-100">
            ⚠️ <strong>Warning:</strong> These actions cannot be undone. Use only when necessary.
          </p>
        </div>
      </CardContent>
    </Card>
  )
}
