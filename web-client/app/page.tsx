"use client"

import { useState } from "react"
import { Activity } from "lucide-react"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { ThemeToggle } from "@/components/theme-toggle"
import { SearchInterface } from "@/components/search-interface"
import { StatsDashboard } from "@/components/stats-dashboard"
import { HealthCheck } from "@/components/health-check"
import { AdminControls } from "@/components/admin-controls"
import type { QuestionResponse } from "@/lib/types"

export default function Home() {
  // Lift search state to page level to persist across tab switches
  const [question, setQuestion] = useState("")
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<QuestionResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="container flex h-16 items-center justify-between px-4 md:px-8">
          <div className="flex items-center gap-2">
            <Activity className="h-6 w-6" />
            <h1 className="text-xl font-bold">Care Beacon</h1>
          </div>
          <div className="flex items-center gap-4">
            <ThemeToggle />
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container px-4 md:px-8 py-8">
        <div className="space-y-8">
          {/* Hero Section */}
          <div className="space-y-2">
            <p className="text-muted-foreground text-sm md:text-base max-w-3xl">
              Get evidence-based medical information powered by AI and BC Cancer&apos;s comprehensive resources.
              Ask questions in natural language and receive accurate, cited answers.
            </p>
          </div>

          {/* Tabs */}
          <Tabs defaultValue="search" className="space-y-6">
            <TabsList className="grid w-full grid-cols-3 md:w-auto md:inline-flex">
              <TabsTrigger value="search">Search</TabsTrigger>
              <TabsTrigger value="stats">Statistics</TabsTrigger>
              <TabsTrigger value="admin">Admin</TabsTrigger>
            </TabsList>

            {/* Search Tab */}
            <TabsContent value="search" className="space-y-6">
              <SearchInterface
                question={question}
                setQuestion={setQuestion}
                loading={loading}
                setLoading={setLoading}
                result={result}
                setResult={setResult}
                error={error}
                setError={setError}
              />
            </TabsContent>

            {/* Statistics Tab */}
            <TabsContent value="stats" className="space-y-6">
              <StatsDashboard />
            </TabsContent>

            {/* Admin Tab */}
            <TabsContent value="admin" className="space-y-6">
              <div className="grid gap-6 lg:grid-cols-2">
                <AdminControls />
                <HealthCheck />
              </div>
            </TabsContent>
          </Tabs>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t mt-12">
        <div className="container px-4 md:px-8 py-6">
          <div className="flex flex-col md:flex-row items-center justify-between gap-4 text-sm text-muted-foreground">
            <p className="text-xs">
              ⚠️ For educational purposes only. Consult healthcare professionals for medical advice.
            </p>
          </div>
        </div>
      </footer>
    </div>
  )
}
