export const UNTITLED = "Untitled conversation"

/** Title to show for a thread; the API returns null until a thread is titled. */
export function displayTitle(title: string | null | undefined): string {
  return title && title.trim() ? title : UNTITLED
}
