"use client"

import { useState } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { channels } from "@/lib/api"
import { toast } from "sonner"
import { X } from "lucide-react"

const CHANNEL_TYPES = ["telegram", "slack", "discord", "whatsapp", "email", "webhook", "exchange"]

interface CreateChannelDialogProps {
  open: boolean
  onClose: () => void
}

export function CreateChannelDialog({ open, onClose }: CreateChannelDialogProps) {
  const qc = useQueryClient()
  const [name, setName] = useState("")
  const [type, setType] = useState("telegram")
  const [configStr, setConfigStr] = useState("{}")
  const [jsonError, setJsonError] = useState("")

  const create = useMutation({
    mutationFn: () => {
      const config = JSON.parse(configStr)
      return channels.create({ name, channel_type: type, config })
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["channels"] })
      toast.success("Channel created")
      onClose()
    },
    onError: (e: Error) => toast.error(e.message),
  })

  const validateJson = (v: string) => {
    setConfigStr(v)
    try { JSON.parse(v); setJsonError("") } catch { setJsonError("Invalid JSON") }
  }

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="w-full max-w-lg rounded-2xl border border-slate-700 bg-slate-900 p-6 shadow-2xl">
        <div className="mb-5 flex items-center justify-between">
          <h2 className="text-base font-semibold text-slate-100">New Channel</h2>
          <button onClick={onClose} className="text-slate-500 hover:text-slate-300">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="space-y-4">
          <div>
            <label className="mb-1 block text-xs text-slate-400">Name</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-100 outline-none focus:border-emerald-500"
              placeholder="My Channel"
            />
          </div>

          <div>
            <label className="mb-1 block text-xs text-slate-400">Type</label>
            <select
              value={type}
              onChange={(e) => setType(e.target.value)}
              className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-100 outline-none focus:border-emerald-500"
            >
              {CHANNEL_TYPES.map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="mb-1 block text-xs text-slate-400">Config (JSON)</label>
            <textarea
              value={configStr}
              onChange={(e) => validateJson(e.target.value)}
              rows={6}
              className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 font-mono text-xs text-slate-100 outline-none focus:border-emerald-500 resize-none"
              placeholder='{"bot_token": "...", "chat_id": "..."}'
            />
            {jsonError && <p className="mt-1 text-xs text-rose-400">{jsonError}</p>}
          </div>
        </div>

        <div className="mt-5 flex gap-3">
          <button
            onClick={() => create.mutate()}
            disabled={create.isPending || !name || !!jsonError}
            className="flex-1 rounded-lg bg-emerald-500 py-2.5 text-sm font-semibold text-slate-950 hover:bg-emerald-400 disabled:opacity-50 transition-colors"
          >
            {create.isPending ? "Creating…" : "Create Channel"}
          </button>
          <button
            onClick={onClose}
            className="flex-1 rounded-lg border border-slate-700 py-2.5 text-sm font-semibold text-slate-300 hover:bg-slate-800 transition-colors"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  )
}
