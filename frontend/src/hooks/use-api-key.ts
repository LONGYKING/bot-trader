"use client"

import { create } from "zustand"
import { persist } from "zustand/middleware"

interface ApiKeyStore {
  apiKey: string
  setApiKey: (key: string) => void
  clearApiKey: () => void
}

export const useApiKeyStore = create<ApiKeyStore>()(
  persist(
    (set) => ({
      apiKey: "",
      setApiKey: (key) => set({ apiKey: key }),
      clearApiKey: () => set({ apiKey: "" }),
    }),
    { name: "bt_api_key" }
  )
)

export function useApiKey() {
  return useApiKeyStore((s) => s.apiKey)
}
