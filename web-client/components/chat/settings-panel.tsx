"use client"

import { Checkbox } from "@/components/ui/checkbox"
import { Slider } from "@/components/ui/slider"
import { ALL_SOURCES } from "@/lib/settings"
import type { ThreadSettings } from "@/lib/types"

export function SettingsPanel({
  settings,
  onChange,
}: {
  settings: ThreadSettings
  onChange: (s: ThreadSettings) => void
}) {
  const toggle = (source: string) => {
    const has = settings.sources.includes(source)
    // The last remaining source cannot be unchecked.
    if (has && settings.sources.length === 1) return
    const sources = has
      ? settings.sources.filter((s) => s !== source)
      : ALL_SOURCES.filter((s) => s === source || settings.sources.includes(s))
    onChange({ ...settings, sources })
  }

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <div className="text-sm font-medium text-muted-foreground">Search in:</div>
        <div className="space-y-2">
          {ALL_SOURCES.map((source, i) => {
            const checked = settings.sources.includes(source)
            const locked = checked && settings.sources.length === 1
            return (
              <div key={source} className="flex items-center space-x-2">
                <Checkbox
                  id={`chat-source-${i}`}
                  checked={checked}
                  disabled={locked}
                  onCheckedChange={() => toggle(source)}
                />
                <label
                  htmlFor={`chat-source-${i}`}
                  className={`text-sm ${locked ? "cursor-not-allowed opacity-50" : "cursor-pointer"}`}
                >
                  {source}
                </label>
              </div>
            )
          })}
        </div>
      </div>
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <div className="text-sm font-medium text-muted-foreground">Minimum similarity score:</div>
          <div className="text-sm font-medium">{Math.round(settings.min_similarity * 100)}%</div>
        </div>
        <Slider
          value={[settings.min_similarity]}
          onValueChange={(v) => onChange({ ...settings, min_similarity: v[0] })}
          min={0}
          max={1}
          step={0.05}
          aria-label="Minimum similarity score"
        />
        <div className="text-xs text-muted-foreground">
          Only sources with at least this similarity score will be used. Lower values return more
          sources.
        </div>
      </div>
    </div>
  )
}
