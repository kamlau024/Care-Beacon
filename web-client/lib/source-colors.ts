/**
 * Shared color scheme for medical data sources
 * Provides consistent styling across badges, charts, and UI elements
 */

export type SourceName = "BC Cancer" | "Canadian Cancer Society" | "Cleveland Clinic"

interface SourceColorScheme {
  // Chart colors (HSL for Recharts)
  chart: string
  // Badge colors (Tailwind classes for light/dark themes)
  badge: string
  // Hex color for general use
  hex: string
}

/**
 * Color scheme mapping for each data source
 * - BC Cancer: Blue
 * - Canadian Cancer Society: Green
 * - Cleveland Clinic: Orange
 */
export const SOURCE_COLORS: Record<SourceName, SourceColorScheme> = {
  "BC Cancer": {
    chart: "hsl(217, 91%, 60%)", // Blue
    badge: "bg-blue-100 text-blue-700 border-blue-200 dark:bg-blue-900/30 dark:text-blue-400 dark:border-blue-800",
    hex: "#4A90E2",
  },
  "Canadian Cancer Society": {
    chart: "hsl(142, 76%, 36%)", // Green
    badge: "bg-green-100 text-green-700 border-green-200 dark:bg-green-900/30 dark:text-green-400 dark:border-green-800",
    hex: "#16A34A",
  },
  "Cleveland Clinic": {
    chart: "hsl(24, 95%, 53%)", // Orange
    badge: "bg-orange-100 text-orange-700 border-orange-200 dark:bg-orange-900/30 dark:text-orange-400 dark:border-orange-800",
    hex: "#F97316",
  },
}

/**
 * Default/fallback color scheme for unknown sources
 */
const DEFAULT_COLORS: SourceColorScheme = {
  chart: "hsl(0, 0%, 60%)", // Gray
  badge: "bg-gray-100 text-gray-700 border-gray-200 dark:bg-gray-900/30 dark:text-gray-400 dark:border-gray-800",
  hex: "#9CA3AF",
}

/**
 * Get chart color (HSL) for a data source
 * Used in Recharts donut charts
 */
export function getSourceChartColor(source: string): string {
  return SOURCE_COLORS[source as SourceName]?.chart || DEFAULT_COLORS.chart
}

/**
 * Get badge styling classes for a data source
 * Used in source badges with light/dark theme support
 */
export function getSourceBadgeStyle(source: string): string {
  return SOURCE_COLORS[source as SourceName]?.badge || DEFAULT_COLORS.badge
}

/**
 * Get hex color for a data source
 * Used for general styling purposes
 */
export function getSourceHexColor(source: string): string {
  return SOURCE_COLORS[source as SourceName]?.hex || DEFAULT_COLORS.hex
}

/**
 * List of all available data sources
 */
export const DATA_SOURCES: SourceName[] = [
  "BC Cancer",
  "Canadian Cancer Society",
  "Cleveland Clinic",
]
