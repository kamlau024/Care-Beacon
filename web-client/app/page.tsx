"use client"

import { useState } from "react"
import { Activity } from "lucide-react"
import {
  NavigationMenu,
  NavigationMenuItem,
  NavigationMenuList,
  navigationMenuTriggerStyle,
} from "@/components/ui/navigation-menu"
import { ThemeToggle } from "@/components/theme-toggle"
import { SearchInterface } from "@/components/search-interface"
import { Chat } from "@/components/chat/chat"
import { StatsDashboard } from "@/components/stats-dashboard"
import { cn } from "@/lib/utils"
import type { QuestionResponse } from "@/lib/types"

type Page = "search" | "chat" | "stats"

// The selected tab gets a warm grey (Tailwind stone) in both themes. data-active is left off (not "false") on
// other tabs, because the shared style's data-[active] selector matches any value.
function navTabClass(active: boolean) {
  return cn(
    navigationMenuTriggerStyle(),
    "gap-1.5",
    active &&
      "bg-stone-200 text-stone-900 hover:bg-stone-300 hover:text-stone-900 focus:bg-stone-200 focus:text-stone-900 dark:bg-stone-700 dark:text-stone-50 dark:hover:bg-stone-600 dark:hover:text-stone-50 dark:focus:bg-stone-700 dark:focus:text-stone-50"
  )
}

export default function Home() {
  // Navigation state
  const [currentPage, setCurrentPage] = useState<Page>("chat")

  // Lift search state to page level to persist across navigation
  const [question, setQuestion] = useState("")
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<QuestionResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="container max-w-6xl mx-auto flex h-16 items-center justify-between px-4 md:px-8">
          <div className="flex items-center gap-2 sm:gap-6">
            <div className="flex items-center gap-2">
              <Activity className="h-6 w-6" />
              <h1 className="sr-only text-xl font-bold sm:not-sr-only">Care Beacon</h1>
            </div>

            {/* Navigation Menu */}
            <NavigationMenu>
              <NavigationMenuList>
                <NavigationMenuItem>
                  <button
                    className={navTabClass(currentPage === "chat")}
                    onClick={() => setCurrentPage("chat")}
                    aria-current={currentPage === "chat" ? "page" : undefined}
                  >
                    Chat
                    <span className="rounded-full bg-blue-600 px-1.5 py-0.5 text-[10px] font-semibold uppercase leading-none tracking-wide text-white">
                      New
                    </span>
                  </button>
                </NavigationMenuItem>
                <NavigationMenuItem>
                  <button
                    className={navTabClass(currentPage === "search")}
                    onClick={() => setCurrentPage("search")}
                    aria-current={currentPage === "search" ? "page" : undefined}
                  >
                    Search
                  </button>
                </NavigationMenuItem>
                <NavigationMenuItem>
                  <button
                    className={navTabClass(currentPage === "stats")}
                    onClick={() => setCurrentPage("stats")}
                    aria-current={currentPage === "stats" ? "page" : undefined}
                  >
                    Statistics
                  </button>
                </NavigationMenuItem>
              </NavigationMenuList>
            </NavigationMenu>
          </div>

          <div className="flex items-center gap-4">
            <ThemeToggle />
          </div>
        </div>
      </header>

      {/* Main Content - Centered */}
      <main className="container max-w-6xl mx-auto px-4 md:px-8 py-8">
        <div className="space-y-8">
          {/* Page Content */}
          {currentPage === "search" && (
            <div className="space-y-6">
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
            </div>
          )}

          {currentPage === "chat" && <Chat />}

          {currentPage === "stats" && (
            <div className="space-y-6">
              <StatsDashboard />
            </div>
          )}
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t mt-12">
        <div className="container max-w-6xl mx-auto px-4 md:px-8 py-6">
          <div className="flex flex-col md:flex-row items-center justify-center gap-4 text-sm text-muted-foreground">
            <p className="text-xs text-center">
              ⚠️ For educational purposes only. Consult healthcare professionals for medical advice.
            </p>
          </div>
        </div>
      </footer>
    </div>
  )
}
