import { api } from "./client"

/** One line of what Frank has learned about the person's taste (spec 09). */
export interface TasteLine {
  id: string
  statement: string
  said_by_you: boolean
  edited: boolean
  about: string
  updated_at: string
}

export function listTaste(): Promise<{ items: TasteLine[] }> {
  return api.get("/taste")
}

export function editTaste(id: string, statement: string): Promise<TasteLine> {
  return api.patch(`/taste/${id}`, { statement })
}

export async function forgetTaste(id: string): Promise<void> {
  await api.delete(`/taste/${id}`)
}

export async function forgetAllTaste(): Promise<void> {
  await api.delete("/taste")
}
