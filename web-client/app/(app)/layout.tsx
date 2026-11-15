import { SiteHeader } from "@/components/site-header"
import { SearchStateProvider } from "@/components/search-state"

// Shared by /chat, /search and /stats. Keep the header, main padding and disclaimer spacing in step with
// the height calc in components/chat/chat.tsx, which subtracts them to fit the chat to the window.
export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-background">
      <SiteHeader />
      <main className="container max-w-6xl mx-auto px-4 md:px-8 pt-4 pb-8">
        {/* Part of the page, not the sticky header: it scrolls away with the content. */}
        <p className="mb-6 text-center text-xs text-muted-foreground">
          ⚠️ For educational purposes only. Consult healthcare professionals for medical advice.
        </p>
        <SearchStateProvider>
          <div className="space-y-8">{children}</div>
        </SearchStateProvider>
      </main>
    </div>
  )
}
