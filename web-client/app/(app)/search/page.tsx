import type { Metadata } from "next"
import { SearchView } from "@/components/search-state"

export const metadata: Metadata = { title: "Search · Care Beacon" }

export default function SearchPage() {
  return (
    <div className="space-y-6">
      <SearchView />
    </div>
  )
}
