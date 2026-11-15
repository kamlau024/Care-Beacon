"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { Activity } from "lucide-react"
import {
  NavigationMenu,
  NavigationMenuItem,
  NavigationMenuList,
  navigationMenuTriggerStyle,
} from "@/components/ui/navigation-menu"
import { ThemeToggle } from "@/components/theme-toggle"
import { cn } from "@/lib/utils"

export const NAV_ITEMS = [
  { href: "/chat", label: "Chat", isNew: true },
  { href: "/search", label: "Search", isNew: false },
  { href: "/stats", label: "Statistics", isNew: false },
] as const

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

/** True when `pathname` is `href` or a page below it (so /chat/anything still lights the Chat tab). */
export function isActivePath(pathname: string | null, href: string): boolean {
  if (!pathname) return false
  return pathname === href || pathname.startsWith(`${href}/`)
}

/** The sticky header shared by the landing page (/) and the app pages (/chat, /search, /stats). */
export function SiteHeader() {
  const pathname = usePathname()

  return (
    <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container max-w-6xl mx-auto flex h-16 items-center justify-between px-4 md:px-8">
        <div className="flex items-center gap-2 sm:gap-6">
          <Link href="/" aria-label="Care Beacon home" className="flex items-center gap-2">
            <Activity className="h-6 w-6" aria-hidden="true" />
            <span className="sr-only text-xl font-bold sm:not-sr-only">Care Beacon</span>
          </Link>

          <NavigationMenu>
            <NavigationMenuList>
              {NAV_ITEMS.map((item) => {
                const active = isActivePath(pathname, item.href)
                return (
                  <NavigationMenuItem key={item.href}>
                    <Link
                      href={item.href}
                      className={navTabClass(active)}
                      aria-current={active ? "page" : undefined}
                    >
                      {item.label}
                      {item.isNew && (
                        <span className="rounded-full bg-blue-600 px-1.5 py-0.5 text-[10px] font-semibold uppercase leading-none tracking-wide text-white">
                          New
                        </span>
                      )}
                    </Link>
                  </NavigationMenuItem>
                )
              })}
            </NavigationMenuList>
          </NavigationMenu>
        </div>

        <div className="flex items-center gap-4">
          <ThemeToggle />
        </div>
      </div>
    </header>
  )
}
