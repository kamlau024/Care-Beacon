"use client"

import { useEffect, useState } from "react"
import { CheckCircle2, XCircle, Loader2, RefreshCw } from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { api, ApiError } from "@/lib/api"
import type { HealthResponse } from "@/lib/types"

export function HealthCheck() {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchHealth = async () => {
    setLoading(true)
    setError(null)

    try {
      const response = await api.getHealth()
      setHealth(response)
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message)
      } else {
        setError("Failed to check system health")
      }
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchHealth()
  }, [])

  if (loading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center h-32">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </CardContent>
      </Card>
    )
  }

  const isHealthy = health?.status === "healthy"
  const allServicesHealthy =
    health?.services.vector_db &&
    health?.services.redis_cache &&
    health?.services.llm_client

  return (
    <Card className={error ? "border-destructive" : ""}>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              System Health
              {!error && !loading && (
                <>
                  {isHealthy && allServicesHealthy ? (
                    <CheckCircle2 className="h-5 w-5 text-green-600 dark:text-green-400" />
                  ) : (
                    <XCircle className="h-5 w-5 text-destructive" />
                  )}
                </>
              )}
            </CardTitle>
            <CardDescription>
              {error ? "Unable to connect to API" : "Real-time system status"}
            </CardDescription>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={fetchHealth}
            disabled={loading}
          >
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {error ? (
          <div className="text-sm text-destructive">{error}</div>
        ) : health ? (
          <div className="space-y-4">
            {/* Overall Status */}
            <div className="flex items-center justify-between pb-4 border-b">
              <div>
                <p className="text-sm font-medium">Overall Status</p>
                <p className="text-xs text-muted-foreground">Version {health.version}</p>
              </div>
              <Badge variant={isHealthy ? "default" : "destructive"}>
                {health.status.toUpperCase()}
              </Badge>
            </div>

            {/* Service Status */}
            <div className="space-y-3">
              <p className="text-sm font-medium">Services</p>

              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  {health.services.vector_db ? (
                    <CheckCircle2 className="h-4 w-4 text-green-600 dark:text-green-400" />
                  ) : (
                    <XCircle className="h-4 w-4 text-destructive" />
                  )}
                  <span className="text-sm">Vector Database</span>
                </div>
                <Badge
                  variant={health.services.vector_db ? "default" : "destructive"}
                  className="text-xs"
                >
                  {health.services.vector_db ? "Connected" : "Disconnected"}
                </Badge>
              </div>

              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  {health.services.redis_cache ? (
                    <CheckCircle2 className="h-4 w-4 text-green-600 dark:text-green-400" />
                  ) : (
                    <XCircle className="h-4 w-4 text-destructive" />
                  )}
                  <span className="text-sm">Redis Cache</span>
                </div>
                <Badge
                  variant={health.services.redis_cache ? "default" : "destructive"}
                  className="text-xs"
                >
                  {health.services.redis_cache ? "Connected" : "Disconnected"}
                </Badge>
              </div>

              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  {health.services.llm_client ? (
                    <CheckCircle2 className="h-4 w-4 text-green-600 dark:text-green-400" />
                  ) : (
                    <XCircle className="h-4 w-4 text-destructive" />
                  )}
                  <span className="text-sm">LLM Client</span>
                </div>
                <Badge
                  variant={health.services.llm_client ? "default" : "destructive"}
                  className="text-xs"
                >
                  {health.services.llm_client ? "Ready" : "Not Ready"}
                </Badge>
              </div>
            </div>

            {/* Timestamp */}
            <div className="pt-4 border-t">
              <p className="text-xs text-muted-foreground">
                Last checked: {new Date(health.timestamp).toLocaleString()}
              </p>
            </div>
          </div>
        ) : null}
      </CardContent>
    </Card>
  )
}
