"use client"

import { useState, useRef, useEffect } from "react"
import { Download, Loader2, CheckCircle2, XCircle, AlertTriangle, Cloud } from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

type DownloadStatus = "idle" | "running" | "success" | "error"

export function DatabaseDownload() {
  const [status, setStatus] = useState<DownloadStatus>("idle")
  const [progress, setProgress] = useState(0)
  const [currentFile, setCurrentFile] = useState("")
  const [filesDownloaded, setFilesDownloaded] = useState(0)
  const [totalFiles, setTotalFiles] = useState(0)
  const [elapsedSeconds, setElapsedSeconds] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [remoteUrl, setRemoteUrl] = useState("")
  const eventSourceRef = useRef<EventSource | null>(null)

  // Load URL from localStorage on mount
  useEffect(() => {
    const savedUrl = localStorage.getItem("vectordb_remote_url")
    if (savedUrl) {
      setRemoteUrl(savedUrl)
    }
  }, [])

  const handleStartDownload = async () => {
    // Validate URL
    if (!remoteUrl.trim()) {
      setError("Please enter a remote URL")
      return
    }

    // Save URL to localStorage for next time
    localStorage.setItem("vectordb_remote_url", remoteUrl.trim())

    // Confirmation dialog
    const confirmed = window.confirm(
      "This will download the pre-built vector database from cloud storage.\n\n" +
      "The existing database will be backed up automatically.\n\n" +
      `Remote URL: ${remoteUrl}\n\n` +
      "Download size: ~1.3GB (31 files)\n" +
      "Estimated time: 2-5 minutes\n\n" +
      "Continue?"
    )

    if (!confirmed) {
      return
    }

    setStatus("running")
    setProgress(0)
    setCurrentFile("")
    setFilesDownloaded(0)
    setTotalFiles(0)
    setElapsedSeconds(0)
    setError(null)

    // Start timer
    const startTime = Date.now()
    const timer = setInterval(() => {
      setElapsedSeconds(Math.floor((Date.now() - startTime) / 1000))
    }, 1000)

    // Close any existing EventSource
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
    }

    // Connect to SSE stream with URL parameter
    const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
    const encodedUrl = encodeURIComponent(remoteUrl.trim())
    const eventSource = new EventSource(`${API_BASE_URL}/api/v1/admin/download-db/stream?base_url=${encodedUrl}`)
    eventSourceRef.current = eventSource

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)

        switch (data.type) {
          case "start":
            setCurrentFile("Starting download...")
            break

          case "progress":
            setProgress(data.percent || 0)
            setCurrentFile(data.message || "")

            // Extract file count from message if available
            const match = data.message?.match(/Downloading (\d+)\/(\d+):/)
            if (match) {
              setFilesDownloaded(parseInt(match[1]))
              setTotalFiles(parseInt(match[2]))
            }
            break

          case "complete":
            clearInterval(timer)
            setStatus("success")
            setProgress(100)
            setCurrentFile("✅ Download complete!")
            setFilesDownloaded(data.files_downloaded || 0)
            eventSource.close()
            break

          case "error":
            clearInterval(timer)
            setStatus("error")
            setError(data.message)
            setCurrentFile(`❌ Error: ${data.message}`)
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
      setError("Connection to server lost")
      setCurrentFile("❌ Connection error")
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
        return <Cloud className="h-5 w-5 text-purple-600 dark:text-purple-400" />
    }
  }

  const getStatusBadge = () => {
    switch (status) {
      case "running":
        return <Badge className="bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200">Downloading</Badge>
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
            <CardTitle>Database Download</CardTitle>
          </div>
          {getStatusBadge()}
        </div>
        <CardDescription>
          Download pre-built vector database from cloud storage
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Remote URL Input */}
        <div className="space-y-2">
          <Label htmlFor="remote-url" className="text-sm font-medium">
            Remote Storage URL
          </Label>
          <div className="flex gap-2">
            <Input
              id="remote-url"
              type="url"
              placeholder="https://storage.googleapis.com/your-bucket/"
              value={remoteUrl}
              onChange={(e) => setRemoteUrl(e.target.value)}
              disabled={status === "running"}
              className="flex-1"
            />
            <Button
              variant="default"
              size="default"
              onClick={handleStartDownload}
              disabled={status === "running" || !remoteUrl.trim()}
              className="shrink-0 bg-purple-600 hover:bg-purple-700"
            >
              {status === "running" ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Downloading...
                </>
              ) : (
                <>
                  <Download className="mr-2 h-4 w-4" />
                  Download
                </>
              )}
            </Button>
          </div>
          <p className="text-xs text-muted-foreground">
            Base URL to your cloud storage bucket (must end with /). The vector_db/ folder (with manifest inside) should be at this location.
          </p>
        </div>

        {/* Example URLs */}
        <div className="rounded-lg bg-muted p-3 space-y-2">
          <p className="text-xs font-medium text-muted-foreground">Example URLs:</p>
          <div className="space-y-1">
            <button
              onClick={() => setRemoteUrl("https://storage.googleapis.com/care-beacon-vectordb/")}
              disabled={status === "running"}
              className="text-xs text-left text-blue-600 dark:text-blue-400 hover:underline block w-full"
            >
              • Google Cloud Storage: https://storage.googleapis.com/bucket-name/
            </button>
            <button
              onClick={() => setRemoteUrl("https://bucket-name.s3.amazonaws.com/")}
              disabled={status === "running"}
              className="text-xs text-left text-blue-600 dark:text-blue-400 hover:underline block w-full"
            >
              • AWS S3: https://bucket-name.s3.amazonaws.com/
            </button>
          </div>
        </div>

        {/* Progress Display */}
        {status === "running" && (
          <div className="rounded-lg bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800 p-4 space-y-3">
            <div className="flex items-center justify-between">
              <div className="text-sm font-medium text-blue-900 dark:text-blue-100">
                Download in progress...
              </div>
              <div className="text-sm font-mono text-blue-900 dark:text-blue-100">
                {formatTime(elapsedSeconds)}
              </div>
            </div>

            {/* Progress Bar */}
            <div className="space-y-2">
              <Progress value={progress} className="h-2" />
              <div className="flex justify-between items-center text-xs">
                <span className="text-blue-700 dark:text-blue-300">
                  {progress}%
                </span>
                {totalFiles > 0 && (
                  <span className="text-blue-700 dark:text-blue-300">
                    {filesDownloaded}/{totalFiles} files
                  </span>
                )}
              </div>
            </div>

            {/* Current file */}
            <div className="rounded border border-blue-300 dark:border-blue-700 bg-blue-100 dark:bg-blue-900 p-3">
              <div className="font-mono text-xs text-blue-900 dark:text-blue-100 truncate">
                {currentFile || "Initializing..."}
              </div>
            </div>
          </div>
        )}

        {/* Success Result */}
        {status === "success" && (
          <div className="rounded-lg bg-green-50 dark:bg-green-950 border border-green-200 dark:border-green-800 p-4 space-y-3">
            <div className="flex items-start gap-2">
              <CheckCircle2 className="h-5 w-5 text-green-600 dark:text-green-400 shrink-0 mt-0.5" />
              <div className="flex-1 space-y-2">
                <div className="text-sm font-medium text-green-900 dark:text-green-100">
                  Database downloaded successfully!
                </div>

                <div className="grid grid-cols-2 gap-3 mt-3">
                  <div className="space-y-1">
                    <div className="text-xs text-green-700 dark:text-green-300">Files Downloaded</div>
                    <div className="text-lg font-semibold text-green-900 dark:text-green-100">
                      {filesDownloaded}
                    </div>
                  </div>
                  <div className="space-y-1">
                    <div className="text-xs text-green-700 dark:text-green-300">Time</div>
                    <div className="text-lg font-semibold text-green-900 dark:text-green-100">
                      {formatTime(elapsedSeconds)}
                    </div>
                  </div>
                </div>

                <div className="text-xs text-green-700 dark:text-green-300 mt-2">
                  The database is now ready to use. You can start querying immediately.
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Error Result */}
        {status === "error" && (
          <div className="rounded-lg bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 p-4 space-y-2">
            <div className="flex items-start gap-2">
              <XCircle className="h-5 w-5 text-red-600 dark:text-red-400 shrink-0 mt-0.5" />
              <div className="flex-1 space-y-1">
                <div className="text-sm font-medium text-red-900 dark:text-red-100">
                  Download failed
                </div>
                {error && (
                  <div className="text-xs text-red-800 dark:text-red-200 font-mono">
                    {error}
                  </div>
                )}
                <div className="text-xs text-red-700 dark:text-red-300 mt-2">
                  Your existing database has been restored from backup.
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Info */}
        <div className="rounded-lg bg-purple-50 dark:bg-purple-950 border border-purple-200 dark:border-purple-800 p-3">
          <div className="flex items-start gap-2">
            <AlertTriangle className="h-4 w-4 text-purple-600 dark:text-purple-400 shrink-0 mt-0.5" />
            <div className="text-xs text-purple-900 dark:text-purple-100 space-y-1">
              <p>
                <strong>Note:</strong> The download will automatically backup your existing database before starting.
              </p>
              <p className="mt-1">
                If download fails, your backup will be automatically restored.
              </p>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
