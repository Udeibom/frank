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
