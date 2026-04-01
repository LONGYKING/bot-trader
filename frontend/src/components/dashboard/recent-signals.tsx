"use client"

import { useQuery } from "@tanstack/react-query"
import { signals } from "@/lib/api"
import { SignalBadge } from "@/components/shared/signal-badge"
import { fmtAgo } from "@/lib/utils"
import { Zap } from "lucide-react"
import { EmptyState } from "@/components/shared/empty-state"

export function RecentSignals() {
  const { data, isLoading } = useQuery({
    queryKey: ["signals", "recent"],
    queryFn: () => signals.list({ page: 1, page_size: 10 }),
    refetchInterval: 30_000,
  })

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900">
      <div className="border-b border-slate-800 px-5 py-4">
        <h2 className="text-sm font-semibold text-slate-100">Recent Signals</h2>
      </div>
      <div className="divide-y divide-slate-800/60">
        {isLoading ? (
          Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="flex items-center gap-3 px-5 py-3">
              <div className="h-6 w-12 animate-pulse rounded bg-slate-800" />
              <div className="h-4 w-20 animate-pulse rounded bg-slate-800" />
              <div className="ml-auto h-4 w-16 animate-pulse rounded bg-slate-800" />
            </div>
          ))
        ) : !data?.items.length ? (
          <EmptyState icon={Zap} title="No signals yet" className="py-10" />
        ) : (
          data.items.map((s) => (
            <div key={s.id} className="flex items-center gap-3 px-5 py-3 hover:bg-slate-800/30 transition-colors">
              <SignalBadge value={s.signal_value} showLabel />
              <span className="text-sm font-medium text-slate-200">{s.asset}</span>
              <span className="text-xs text-slate-500">{s.timeframe}</span>
              <span className="ml-auto text-xs text-slate-500 tabular-nums">{fmtAgo(s.entry_time)}</span>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
