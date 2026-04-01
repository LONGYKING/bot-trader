"use client"

import { use } from "react"
import { useQuery } from "@tanstack/react-query"
import { strategies } from "@/lib/api"
import { SignalBadge } from "@/components/shared/signal-badge"
import { StatusDot } from "@/components/shared/status-dot"
import { DataTable } from "@/components/shared/data-table"
import { StatCard } from "@/components/shared/stat-card"
import { fmtDate, fmtPct, pnlColor } from "@/lib/utils"
import { ArrowLeft, Trophy, BarChart2, Zap, Target } from "lucide-react"
import Link from "next/link"
import { useState } from "react"
import type { Signal } from "@/lib/types"

export default function StrategyDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const [page, setPage] = useState(1)

  const { data: strategy, isLoading } = useQuery({
    queryKey: ["strategy", id],
    queryFn: () => strategies.get(id),
  })

  const { data: perf } = useQuery({
    queryKey: ["strategy", id, "performance"],
    queryFn: () => strategies.performance(id),
  })

  const { data: signalsData } = useQuery({
    queryKey: ["strategy", id, "signals", page],
    queryFn: () => strategies.signals(id, { page, page_size: 20 }),
  })

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-48 animate-pulse rounded bg-slate-800" />
        <div className="grid grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-28 animate-pulse rounded-xl bg-slate-800" />
          ))}
        </div>
      </div>
    )
  }

  if (!strategy) return <p className="text-slate-400">Strategy not found</p>

  const columns = [
    {
      key: "signal",
      header: "Signal",
      render: (s: Signal) => <SignalBadge value={s.signal_value} showLabel />,
    },
    {
      key: "asset",
      header: "Asset",
      render: (s: Signal) => <span className="font-medium">{s.asset}</span>,
    },
    {
      key: "entry_price",
      header: "Entry Price",
      render: (s: Signal) => s.entry_price?.toFixed(4) ?? "—",
    },
    {
      key: "pnl",
      header: "PnL",
      render: (s: Signal) => (
        <span className={pnlColor(s.is_profitable ? 0.01 : s.is_profitable === false ? -0.01 : null)}>
          {s.is_profitable == null ? "—" : s.is_profitable ? "Win" : "Loss"}
        </span>
      ),
    },
    {
      key: "time",
      header: "Time",
      render: (s: Signal) => <span className="tabular-nums text-slate-500">{fmtDate(s.entry_time)}</span>,
    },
  ]

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Link href="/strategies" className="text-slate-400 hover:text-slate-200 transition-colors">
          <ArrowLeft className="h-4 w-4" />
        </Link>
        <div>
          <h1 className="text-lg font-semibold text-slate-100">{strategy.name}</h1>
          <div className="flex items-center gap-2 mt-0.5">
            <StatusDot status={strategy.is_active ? "active" : "inactive"} label={strategy.is_active ? "Active" : "Inactive"} />
            <span className="text-xs text-slate-500">·</span>
            <span className="text-xs text-slate-500">{strategy.strategy_class}</span>
          </div>
        </div>
      </div>

      {perf && (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <StatCard label="Total Signals" value={perf.total_signals} icon={Zap} />
          <StatCard label="Profitable" value={perf.profitable_signals} icon={Target} />
          <StatCard
            label="Win Rate"
            value={`${(perf.win_rate * 100).toFixed(1)}%`}
            icon={Trophy}
            trend={perf.win_rate >= 0.5 ? "up" : "down"}
          />
          <StatCard
            label="Avg PnL"
            value={fmtPct(perf.avg_pnl_pct)}
            icon={BarChart2}
            trend={perf.avg_pnl_pct >= 0 ? "up" : "down"}
          />
        </div>
      )}

      <div className="rounded-xl border border-slate-800 bg-slate-900 p-5">
        <h2 className="mb-4 text-sm font-semibold text-slate-100">Configuration</h2>
        <div className="grid grid-cols-2 gap-x-8 gap-y-2 text-sm sm:grid-cols-4">
          {[
            ["Asset", strategy.asset],
            ["Timeframe", strategy.timeframe],
            ["Exchange", strategy.exchange],
            ["Trade Type", strategy.trade_type],
            ["Interval", `${strategy.interval_minutes}m`],
            ["Version", strategy.version],
          ].map(([k, v]) => (
            <div key={k} className="flex justify-between border-b border-slate-800/60 py-1.5">
              <span className="text-slate-500">{k}</span>
              <span className="text-slate-300 font-medium">{v}</span>
            </div>
          ))}
        </div>
      </div>

      <div>
        <h2 className="mb-3 text-sm font-semibold text-slate-100">Signals</h2>
        <DataTable
          columns={columns}
          data={signalsData?.items ?? []}
          keyFn={(s) => s.id}
          page={page}
          pages={signalsData?.pages ?? 1}
          onPageChange={setPage}
        />
      </div>
    </div>
  )
}
