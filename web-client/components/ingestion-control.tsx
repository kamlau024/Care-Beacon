"use client"

import { useState, useRef, useEffect } from "react"
import { Upload, Loader2, CheckCircle2, XCircle, AlertTriangle } from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { api, ApiError } from "@/lib/api"
import type { IngestionResponse } from "@/lib/types"

type IngestionStatus = "idle" | "running" | "success" | "error"

export function IngestionControl() {
  const [status, setStatus] = useState<IngestionStatus>("idle")
  const [result, setResult] = useState<IngestionResponse | null>(null)
  const [startTime, setStartTime] = useState<number | null>(null)
  const [elapsedSeconds, setElapsedSeconds] = useState(0)
  const [logs, setLogs] = useState<string[]>([])
  const eventSourceRef = useRef<EventSource | null>(null)
  const logsEndRef = useRef<HTMLDivElement>(null)

  // Auto-scroll logs to bottom
  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [logs])

  const handleStartIngestion = async () => {
    // Confirmation dialog
    const confirmed = window.confirm(
      "This will re-ingest all articles and may take 5-10 minutes.\n\n" +
      "Cost: ~$0.02 for embeddings\n\n" +
      "Continue?"
    )

    if (!confirmed) {
      return
    }

    setStatus("running")
    setResult(null)
    setLogs([])
    setStartTime(Date.now())
    setElapsedSeconds(0)

    // Start timer
    const timer = setInterval(() => {
      setElapsedSeconds((prev) => prev + 1)
    }, 1000)

    // Close any existing EventSource
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
    }

    // Connect to SSE stream
    const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
    const eventSource = new EventSource(`${API_BASE_URL}/api/v1/admin/ingest/stream`)
    eventSourceRef.current = eventSource

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)

        switch (data.type) {
          case "start":
            setLogs((prev) => [...prev, "Starting ingestion..."])
            break

          case "log":
            setLogs((prev) => [...prev, data.message])
            break

          case "complete":
            clearInterval(timer)
            setStatus("success")
            setLogs((prev) => [...prev, `\n✅ Ingestion completed in ${data.elapsed_seconds}s`])

            // Parse final stats from logs
            const stats: any = {}
            logs.forEach(line => {
              if (line.includes("Total articles processed:")) {
                stats.articles_processed = line.split(":")[1]?.trim()
              } else if (line.includes("Total chunks created:")) {
                stats.chunks_created = line.split(":")[1]?.trim()
              } else if (line.includes("Total cost:")) {
                stats.cost = line.split(":")[1]?.trim()
              }
            })

            setResult({
              message: "Ingestion completed successfully",
              status: "success",
              elapsed_seconds: data.elapsed_seconds,
              stats,
              timestamp: data.timestamp
            })

            eventSource.close()
            break

          case "error":
            clearInterval(timer)
            setStatus("error")
            setLogs((prev) => [...prev, `\n❌ Error: ${data.message}`])
            setResult({
              message: "Ingestion failed",
              status: "error",
              elapsed_seconds: data.elapsed_seconds || 0,
              error: data.message,
              timestamp: new Date().toISOString()
            })
            eventSource.close()
            break
        }
      } catch (err) {
        console.error("Failed to parse SSE message:", err)
      }
    }

    eventSource.onerror = (error) => {
      console.error("SSE error:", error)
      clearInterval(timer)
      setStatus("error")
      setLogs((prev) => [...prev, "\n❌ Connection error"])
      setResult({
        message: "Ingestion failed",
        status: "error",
        elapsed_seconds: (Date.now() - (startTime || Date.now())) / 1000,
        error: "Connection to server lost",
        timestamp: new Date().toISOString()
      })
      eventSource.close()
    }
  }

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins}:${secs.toString().padStart(2, "0")}`
  }

  const getStatusIcon = () => {
    switch (status) {
      case "running":
        return <Loader2 className="h-5 w-5 animate-spin text-blue-600 dark:text-blue-400" />
      case "success":
        return <CheckCircle2 className="h-5 w-5 text-green-600 dark:text-green-400" />
      case "error":
        return <XCircle className="h-5 w-5 text-red-600 dark:text-red-400" />
      default:
        return <Upload className="h-5 w-5 text-orange-600 dark:text-orange-400" />
    }
  }

  const getStatusBadge = () => {
    switch (status) {
      case "running":
        return <Badge className="bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200">Running</Badge>
      case "success":
        return <Badge className="bg-green-100 dark:bg-green-900 text-green-800 dark:text-green-200">Success</Badge>
      case "error":
        return <Badge className="bg-red-100 dark:bg-red-900 text-red-800 dark:text-red-200">Error</Badge>
      default:
        return <Badge variant="outline">Ready</Badge>
    }
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {getStatusIcon()}
            <CardTitle>Data Ingestion</CardTitle>
          </div>
          {getStatusBadge()}
        </div>
        <CardDescription>
          Rebuild the vector database with all articles
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Action Button */}
        <div className="flex items-start justify-between gap-4 p-4 rounded-lg border">
          <div className="flex-1">
            <h4 className="font-medium text-sm mb-1">Trigger Re-ingestion</h4>
            <p className="text-xs text-muted-foreground">
              Re-process all articles and rebuild the vector database. Use this after adding new articles or when database updates are needed.
            </p>
          </div>
          <Button
            variant="default"
            size="sm"
            onClick={handleStartIngestion}
            disabled={status === "running"}
            className="shrink-0"
          >
            {status === "running" ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Running...
              </>
            ) : (
              <>
                <Upload className="mr-2 h-4 w-4" />
                Start
              </>
            )}
          </Button>
        </div>

        {/* Progress Display with Real-time Logs */}
        {status === "running" && (
          <div className="rounded-lg bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800 p-4 space-y-3">
            <div className="flex items-center justify-between">
              <div className="text-sm font-medium text-blue-900 dark:text-blue-100">
                Ingestion in progress...
              </div>
              <div className="text-sm font-mono text-blue-900 dark:text-blue-100">
                {formatTime(elapsedSeconds)}
              </div>
            </div>

            {/* Real-time log viewer */}
            <div className="rounded border border-blue-300 dark:border-blue-700 bg-blue-100 dark:bg-blue-900 p-3 max-h-64 overflow-y-auto">
              <div className="font-mono text-xs text-blue-900 dark:text-blue-100 whitespace-pre-wrap">
                {logs.length === 0 ? (
                  <div className="text-blue-700 dark:text-blue-300">Connecting...</div>
                ) : (
                  logs.map((log, index) => (
                    <div key={index}>{log}</div>
                  ))
                )}
                <div ref={logsEndRef} />
              </div>
            </div>
          </div>
        )}

        {/* Success Result */}
        {status === "success" && result && (
          <div className="rounded-lg bg-green-50 dark:bg-green-950 border border-green-200 dark:border-green-800 p-4 space-y-3">
            <div className="flex items-start gap-2">
              <CheckCircle2 className="h-5 w-5 text-green-600 dark:text-green-400 shrink-0 mt-0.5" />
              <div className="flex-1 space-y-2">
                <div className="text-sm font-medium text-green-900 dark:text-green-100">
                  {result.message}
                </div>

                {result.stats && (
                  <div className="grid grid-cols-3 gap-3 mt-3">
                    {result.stats.articles_processed && (
                      <div className="space-y-1">
                        <div className="text-xs text-green-700 dark:text-green-300">Articles</div>
                        <div className="text-lg font-semibold text-green-900 dark:text-green-100">
                          {result.stats.articles_processed}
                        </div>
                      </div>
                    )}
                    {result.stats.chunks_created && (
                      <div className="space-y-1">
                        <div className="text-xs text-green-700 dark:text-green-300">Chunks</div>
                        <div className="text-lg font-semibold text-green-900 dark:text-green-100">
                          {result.stats.chunks_created}
                        </div>
                      </div>
                    )}
                    {result.stats.cost && (
                      <div className="space-y-1">
                        <div className="text-xs text-green-700 dark:text-green-300">Cost</div>
                        <div className="text-lg font-semibold text-green-900 dark:text-green-100">
                          {result.stats.cost}
                        </div>
                      </div>
                    )}
                  </div>
                )}

                <div className="text-xs text-green-700 dark:text-green-300 mt-2">
                  Completed in {result.elapsed_seconds.toFixed(1)}s
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Error Result */}
        {status === "error" && result && (
          <div className="rounded-lg bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 p-4 space-y-2">
            <div className="flex items-start gap-2">
              <XCircle className="h-5 w-5 text-red-600 dark:text-red-400 shrink-0 mt-0.5" />
              <div className="flex-1 space-y-1">
                <div className="text-sm font-medium text-red-900 dark:text-red-100">
                  {result.message}
                </div>
                {result.error && (
                  <div className="text-xs text-red-800 dark:text-red-200 font-mono">
                    {result.error}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Warning */}
        <div className="rounded-lg bg-orange-50 dark:bg-orange-950 border border-orange-200 dark:border-orange-800 p-3">
          <div className="flex items-start gap-2">
            <AlertTriangle className="h-4 w-4 text-orange-600 dark:text-orange-400 shrink-0 mt-0.5" />
            <p className="text-xs text-orange-900 dark:text-orange-100">
              <strong>Note:</strong> Ingestion will clear the existing database and rebuild from scratch. This process cannot be undone.
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
