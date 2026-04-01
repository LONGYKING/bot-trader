"use client"

import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { admin } from "@/lib/api"
import { fmtDate } from "@/lib/utils"
import { StatusDot } from "@/components/shared/status-dot"
import { toast } from "sonner"
import { KeyRound, Plus, Copy, RefreshCw, Trash2 } from "lucide-react"

export default function AdminPage() {
  const qc = useQueryClient()
  const [showCreate, setShowCreate] = useState(false)
  const [newKeyName, setNewKeyName] = useState("")
  const [revealedKey, setRevealedKey] = useState<string | null>(null)

  const { data: keys, isLoading } = useQuery({
    queryKey: ["admin-keys"],
    queryFn: () => admin.listKeys(),
  })

  const { data: workerStats } = useQuery({
    queryKey: ["worker-stats"],
    queryFn: () => admin.workerStats(),
    refetchInterval: 15_000,
  })

  const createKey = useMutation({
    mutationFn: () => admin.createKey({ name: newKeyName }),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ["admin-keys"] })
      setRevealedKey(res.raw_key)
      setShowCreate(false)
      setNewKeyName("")
      toast.success("API key created — copy it now, it won't be shown again")
    },
    onError: (e: Error) => toast.error(e.message),
  })

  const rotateKey = useMutation({
    mutationFn: (id: string) => admin.rotateKey(id),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ["admin-keys"] })
      setRevealedKey(res.raw_key)
      toast.success("Key rotated — copy the new key now")
    },
    onError: (e: Error) => toast.error(e.message),
  })

  const revokeKey = useMutation({
    mutationFn: (id: string) => admin.revokeKey(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-keys"] })
      toast.success("Key revoked")
    },
    onError: (e: Error) => toast.error(e.message),
  })

  const copyKey = (key: string) => {
    navigator.clipboard.writeText(key)
    toast.success("Copied to clipboard")
  }

  return (
    <div className="space-y-6">
      {/* Worker Status */}
      <div className="rounded-xl border border-slate-800 bg-slate-900 p-5">
        <h2 className="mb-3 text-sm font-semibold text-slate-100">Worker Status</h2>
        {workerStats ? (
          <div className="flex items-center gap-3">
            <StatusDot status={workerStats.status === "ok" ? "active" : "error"} />
            <span className="text-sm text-slate-300">{workerStats.message}</span>
          </div>
        ) : (
          <div className="h-5 w-48 animate-pulse rounded bg-slate-800" />
        )}
      </div>

      {/* Revealed Key Banner */}
      {revealedKey && (
        <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-4">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-xs font-semibold text-emerald-400 mb-1">New API Key (copy now — won&apos;t be shown again)</p>
              <code className="text-sm text-emerald-300 font-mono break-all">{revealedKey}</code>
            </div>
            <button
              onClick={() => copyKey(revealedKey)}
              className="shrink-0 flex items-center gap-1.5 rounded-lg bg-emerald-500/20 px-3 py-2 text-xs font-semibold text-emerald-400 hover:bg-emerald-500/30 transition-colors"
            >
              <Copy className="h-3 w-3" />
              Copy
            </button>
          </div>
          <button
            onClick={() => setRevealedKey(null)}
            className="mt-2 text-xs text-emerald-600 hover:text-emerald-400 transition-colors"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* API Keys */}
      <div className="rounded-xl border border-slate-800 bg-slate-900">
        <div className="flex items-center justify-between border-b border-slate-800 px-5 py-4">
          <h2 className="text-sm font-semibold text-slate-100">API Keys</h2>
          <button
            onClick={() => setShowCreate((v) => !v)}
            className="flex items-center gap-1.5 rounded-lg bg-emerald-500 px-3 py-1.5 text-xs font-semibold text-slate-950 hover:bg-emerald-400 transition-colors"
          >
            <Plus className="h-3 w-3" />
            New Key
          </button>
        </div>

        {showCreate && (
          <div className="border-b border-slate-800 px-5 py-4 flex gap-3">
            <input
              value={newKeyName}
              onChange={(e) => setNewKeyName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && newKeyName && createKey.mutate()}
              placeholder="Key name (e.g. dashboard)"
              className="flex-1 rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-100 placeholder-slate-500 outline-none focus:border-emerald-500"
            />
            <button
              onClick={() => createKey.mutate()}
              disabled={createKey.isPending || !newKeyName}
              className="rounded-lg bg-emerald-500 px-4 py-2 text-sm font-semibold text-slate-950 hover:bg-emerald-400 disabled:opacity-50 transition-colors"
            >
              {createKey.isPending ? "Creating…" : "Create"}
            </button>
          </div>
        )}

        {isLoading ? (
          <div className="p-5 space-y-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="h-10 animate-pulse rounded bg-slate-800" />
            ))}
          </div>
        ) : !keys?.length ? (
          <div className="flex flex-col items-center gap-2 py-10">
            <KeyRound className="h-8 w-8 text-slate-600" />
            <p className="text-sm text-slate-500">No API keys</p>
          </div>
        ) : (
          <div className="divide-y divide-slate-800/60">
            {keys.map((key) => (
              <div key={key.id} className="flex items-center gap-4 px-5 py-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-slate-200">{key.name}</span>
                    <span className={`text-xs px-1.5 py-0.5 rounded ${key.is_active ? "text-emerald-400 bg-emerald-500/10" : "text-slate-500 bg-slate-800"}`}>
                      {key.is_active ? "active" : "revoked"}
                    </span>
                  </div>
                  <div className="flex items-center gap-3 mt-0.5">
                    <code className="text-xs text-slate-500">{key.key_prefix}…</code>
                    {key.last_used_at && (
                      <span className="text-xs text-slate-600">
                        Used {fmtDate(key.last_used_at)}
                      </span>
                    )}
                    {key.created_at && (
                      <span className="text-xs text-slate-600">
                        Created {fmtDate(key.created_at)}
                      </span>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  <button
                    onClick={() => {
                      if (confirm("Rotate this key? The current key will be invalidated.")) {
                        rotateKey.mutate(key.id)
                      }
                    }}
                    disabled={rotateKey.isPending}
                    className="flex h-7 w-7 items-center justify-center rounded-md border border-slate-700 text-slate-400 hover:bg-slate-800 hover:text-slate-200 transition-colors"
                    title="Rotate"
                  >
                    <RefreshCw className="h-3.5 w-3.5" />
                  </button>
                  <button
                    onClick={() => {
                      if (confirm(`Revoke "${key.name}"?`)) revokeKey.mutate(key.id)
                    }}
                    disabled={revokeKey.isPending}
                    className="flex h-7 w-7 items-center justify-center rounded-md border border-slate-700 text-rose-400 hover:bg-rose-500/10 transition-colors"
                    title="Revoke"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
