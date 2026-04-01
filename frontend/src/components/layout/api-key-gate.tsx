"use client"

import { useApiKeyStore } from "@/hooks/use-api-key"
import { useState } from "react"
import { Bot, KeyRound } from "lucide-react"

export function ApiKeyGate({ children }: { children: React.ReactNode }) {
  const { apiKey, setApiKey } = useApiKeyStore()
  const [input, setInput] = useState("")
  const [error, setError] = useState("")

  if (apiKey) return <>{children}</>

  const submit = () => {
    const trimmed = input.trim()
    if (!trimmed) { setError("API key is required"); return }
    if (!trimmed.startsWith("sp_")) { setError('Key must start with "sp_"'); return }
    setApiKey(trimmed)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950">
      <div className="w-full max-w-sm rounded-2xl border border-slate-800 bg-slate-900 p-8 shadow-2xl">
        <div className="mb-6 flex flex-col items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-emerald-500">
            <Bot className="h-6 w-6 text-slate-950" />
          </div>
          <div className="text-center">
            <h1 className="text-lg font-semibold text-slate-100">BotTrader</h1>
            <p className="mt-1 text-sm text-slate-400">Enter your API key to continue</p>
          </div>
        </div>

        <div className="space-y-3">
          <div className="relative">
            <KeyRound className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500" />
            <input
              type="password"
              placeholder="sp_..."
              value={input}
              onChange={(e) => { setInput(e.target.value); setError("") }}
              onKeyDown={(e) => e.key === "Enter" && submit()}
              className="w-full rounded-lg border border-slate-700 bg-slate-800 py-2.5 pl-10 pr-4 text-sm text-slate-100 placeholder-slate-500 outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500/30 transition-all"
            />
          </div>

          {error && <p className="text-xs text-rose-400">{error}</p>}

          <button
            onClick={submit}
            className="w-full rounded-lg bg-emerald-500 py-2.5 text-sm font-semibold text-slate-950 hover:bg-emerald-400 transition-colors"
          >
            Connect
          </button>
        </div>

        <p className="mt-4 text-center text-xs text-slate-500">
          Generate a key at{" "}
          <code className="text-slate-400">make seed-api-key</code>
        </p>
      </div>
    </div>
  )
}
