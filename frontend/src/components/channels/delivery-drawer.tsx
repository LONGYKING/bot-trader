"use client"

import { useQuery } from "@tanstack/react-query"
import { channels } from "@/lib/api"
import { StatusDot } from "@/components/shared/status-dot"
import { fmtDate } from "@/lib/utils"
import { X } from "lucide-react"

interface DeliveryDrawerProps {
  channelId: string | null
  onClose: () => void
}

export function DeliveryDrawer({ channelId, onClose }: DeliveryDrawerProps) {
  const { data, isLoading } = useQuery({
    queryKey: ["channel-deliveries", channelId],
    queryFn: () => channels.deliveries(channelId!, { page_size: 50 }),
    enabled: !!channelId,
  })

  if (!channelId) return null

  return (
    <div className="fixed inset-0 z-50 flex">
      <div className="flex-1" onClick={onClose} />
      <div className="w-full max-w-md bg-slate-900 border-l border-slate-800 flex flex-col h-full shadow-2xl">
        <div className="flex items-center justify-between border-b border-slate-800 px-5 py-4">
          <h2 className="text-sm font-semibold text-slate-100">Delivery History</h2>
          <button onClick={onClose} className="text-slate-500 hover:text-slate-300">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto divide-y divide-slate-800/60">
          {isLoading ? (
            Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="px-5 py-3 space-y-1">
                <div className="h-3 w-32 animate-pulse rounded bg-slate-800" />
                <div className="h-3 w-20 animate-pulse rounded bg-slate-800" />
              </div>
            ))
          ) : !data?.length ? (
            <p className="px-5 py-6 text-sm text-slate-500">No deliveries yet</p>
          ) : (
            data.map((d) => (
              <div key={d.id} className="px-5 py-3">
                <div className="flex items-center justify-between">
                  <StatusDot status={d.status} label={d.status} />
                  <span className="text-xs text-slate-500 tabular-nums">
                    {fmtDate(d.created_at)}
                  </span>
                </div>
                {d.error_message && (
                  <p className="mt-1 text-xs text-rose-400 truncate">{d.error_message}</p>
                )}
                <p className="mt-0.5 text-xs text-slate-600">Attempts: {d.attempt_count}</p>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
