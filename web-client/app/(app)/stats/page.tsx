import type { Metadata } from "next"
import { StatsDashboard } from "@/components/stats-dashboard"

export const metadata: Metadata = { title: "Statistics · Care Beacon" }

export default function StatsPage() {
  return (
    <div className="space-y-6">
      <StatsDashboard />
    </div>
  )
}
