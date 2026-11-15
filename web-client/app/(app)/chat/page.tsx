import type { Metadata } from "next"
import { Chat } from "@/components/chat/chat"

export const metadata: Metadata = { title: "Chat · Care Beacon" }

export default function ChatPage() {
  return <Chat />
}
