"use client"

import { createContext, useContext, useState, type ReactNode } from "react"
import { SearchInterface } from "@/components/search-interface"
import type { QuestionResponse } from "@/lib/types"

type SearchState = {
  question: string
  setQuestion: (value: string) => void
  loading: boolean
  setLoading: (value: boolean) => void
  result: QuestionResponse | null
  setResult: (value: QuestionResponse | null) => void
  error: string | null
  setError: (value: string | null) => void
}

const SearchStateContext = createContext<SearchState | null>(null)

/**
 * Holds the Search page's question and answer. It lives in app/(app)/layout.tsx, which App Router keeps
 * mounted while you move between /chat, /search and /stats, so a Search answer survives a tab switch.
 */
export function SearchStateProvider({ children }: { children: ReactNode }) {
  const [question, setQuestion] = useState("")
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<QuestionResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  return (
    <SearchStateContext.Provider
      value={{ question, setQuestion, loading, setLoading, result, setResult, error, setError }}
    >
      {children}
    </SearchStateContext.Provider>
  )
}

/** The Search page body, wired to the shared state above. */
export function SearchView() {
  const state = useContext(SearchStateContext)
  if (!state) throw new Error("SearchView must be rendered inside SearchStateProvider")
  return <SearchInterface {...state} />
}
