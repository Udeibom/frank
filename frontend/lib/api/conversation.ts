import { api } from "./client"
import type { ConversationMessage, ConversationResponse } from "@/types/api"

export interface IdeaConversationInput {
  message: string
  currentLyrics: string
  selectedText?: string
  history: ConversationMessage[]
}

export async function sendIdeaMessage(
  projectId: string,
  input: IdeaConversationInput,
): Promise<ConversationResponse> {
  return api.post<ConversationResponse>(`/projects/${projectId}/conversation/idea`, {
    message: input.message,
    current_lyrics: input.currentLyrics,
    selected_text: input.selectedText,
    history: input.history,
  })
}

/** One stored exchange line from a room's conversation (backend conversation_store). */
export interface StoredTurn {
  role: "user" | "assistant"
  content: string
  created_at: string
}

/** Everything said in a room before, oldest first, so a reload or another device shows the conversation. */
export async function getRoomHistory(projectId: string, room: string): Promise<StoredTurn[]> {
  return api.get<StoredTurn[]>(`/projects/${projectId}/conversation/${room}/history`)
}
