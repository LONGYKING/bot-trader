"use client"

import { useMutation, useQueryClient } from "@tanstack/react-query"
import { channels } from "@/lib/api"
import type { Channel } from "@/lib/types"
import { StatusDot } from "@/components/shared/status-dot"
import { channelTypeLabel } from "@/lib/utils"
import { toast } from "sonner"
import { Radio, Send, Trash2 } from "lucide-react"

interface ChannelCardProps {
  channel: Channel
  onViewDeliveries: (id: string) => void
}

export function ChannelCard({ channel: c, onViewDeliveries }: ChannelCardProps) {
  const qc = useQueryClient()

  const test = useMutation({
    mutationFn: () => channels.test(c.id),
    onSuccess: (res) => {
      toast[res.success ? "success" : "error"](res.message)
    },
    onError: (e: Error) => toast.error(e.message),
  })

  const remove = useMutation({
    mutationFn: () => channels.delete(c.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["channels"] })
      toast.success("Channel deleted")
    },
    onError: (e: Error) => toast.error(e.message),
  })

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900 p-5 flex flex-col gap-4 hover:border-slate-700 transition-colors">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-800">
            <Radio className="h-4 w-4 text-slate-400" />
          </div>
          <div>
            <p className="text-sm font-semibold text-slate-100">{c.name}</p>
            <p className="text-xs text-slate-500">
              {channelTypeLabel(c.channel_type)}
              {c.config_summary && <span className="ml-1.5 text-slate-600">· {c.config_summary}</span>}
            </p>
          </div>
        </div>
        <StatusDot status={c.health_status ?? (c.is_active ? "active" : "inactive")} />
      </div>

      <div className="flex gap-2">
        <button
          onClick={() => test.mutate()}
          disabled={test.isPending}
          className="flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-slate-800 py-1.5 text-xs font-medium text-slate-300 hover:bg-slate-700 transition-colors"
        >
          <Send className="h-3 w-3" />
          {test.isPending ? "Testing…" : "Test"}
        </button>
        <button
          onClick={() => onViewDeliveries(c.id)}
          className="flex-1 rounded-lg bg-slate-800 py-1.5 text-xs font-medium text-slate-300 hover:bg-slate-700 transition-colors"
        >
          Deliveries
        </button>
        <button
          onClick={() => {
            if (confirm(`Delete "${c.name}"?`)) remove.mutate()
          }}
          disabled={remove.isPending}
          className="flex h-7 w-7 items-center justify-center rounded-lg bg-rose-500/10 text-rose-400 hover:bg-rose-500/20 transition-colors"
        >
          <Trash2 className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  )
}
