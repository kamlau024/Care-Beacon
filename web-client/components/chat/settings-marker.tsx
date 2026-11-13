import { SlidersHorizontal } from "lucide-react"
import { describeSettingsChange } from "@/lib/settings"
import type { SettingsDelta } from "@/lib/types"

export function SettingsMarker({ delta }: { delta: SettingsDelta }) {
  const d = describeSettingsChange(delta)
  return (
    <div className="mx-auto w-full max-w-md rounded-lg border border-dashed bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
      <div className="mb-1 flex items-center gap-1.5 font-medium text-foreground">
        <SlidersHorizontal className="h-3.5 w-3.5" />
        Retrieval settings changed
      </div>
      <div className="break-words">
        <span className="font-medium">Sources:</span> {d.sources}
      </div>
      <div>
        <span className="font-medium">Min similarity:</span> {d.similarity}
      </div>
    </div>
  )
}
