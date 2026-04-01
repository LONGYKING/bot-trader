"use client"

import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { signals } from "@/lib/api"
import { SignalBadge } from "@/components/shared/signal-badge"
import { DataTable } from "@/components/shared/data-table"
import { fmtDate, pnlColor } from "@/lib/utils"
import type { Signal } from "@/lib/types"
import { X } from "lucide-react"

export default function SignalsPage() {
  const [page, setPage] = useState(1)
  const [asset, setAsset] = useState("")
  const [signalValue, setSignalValue] = useState("")

  const { data, isLoading } = useQuery({
    queryKey: ["signals", { page, asset, signalValue }],
    queryFn: () => signals.list({
      page,
      page_size: 25,
      asset: asset || undefined,
      signal_value: signalValue ? Number(signalValue) : undefined,
    }),
  })

  const clearFilters = () => { setAsset(""); setSignalValue(""); setPage(1) }
  const hasFilters = !!asset || !!signalValue

  const columns = [
    {
      key: "signal",
      header: "Signal",
      render: (s: Signal) => <SignalBadge value={s.signal_value} showLabel />,
    },
    {
      key: "asset",
      header: "Asset",
      render: (s: Signal) => <span className="font-medium text-slate-200">{s.asset}</span>,
    },
    {
      key: "timeframe",
      header: "TF",
      render: (s: Signal) => <span className="text-slate-400">{s.timeframe}</span>,
    },
    {
      key: "confidence",
      header: "Confidence",
      render: (s: Signal) => s.confidence != null
        ? <span className="tabular-nums">{(s.confidence * 100).toFixed(0)}%</span>
        : <span className="text-slate-500">—</span>,
    },
    {
      key: "entry_price",
      header: "Entry Price",
      render: (s: Signal) => (
        <span className="tabular-nums">{s.entry_price?.toFixed(4) ?? "—"}</span>
      ),
    },
    {
      key: "pnl",
      header: "Result",
      render: (s: Signal) => (
        <span className={pnlColor(s.is_profitable ? 0.01 : s.is_profitable === false ? -0.01 : null)}>
          {s.is_profitable == null ? "—" : s.is_profitable ? "Win" : "Loss"}
        </span>
      ),
    },
    {
      key: "time",
      header: "Time",
      render: (s: Signal) => (
        <span className="tabular-nums text-slate-500 text-xs">{fmtDate(s.entry_time)}</span>
      ),
    },
  ]

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <input
          value={asset}
          onChange={(e) => { setAsset(e.target.value); setPage(1) }}
          placeholder="Filter by asset…"
          className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-100 placeholder-slate-500 outline-none focus:border-emerald-500 w-44"
        />
        <select
          value={signalValue}
          onChange={(e) => { setSignalValue(e.target.value); setPage(1) }}
          className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-100 outline-none focus:border-emerald-500"
        >
          <option value="">All signals</option>
          <option value="7">+7 Strong Buy</option>
          <option value="3">+3 Buy</option>
          <option value="-3">-3 Sell</option>
          <option value="-7">-7 Strong Sell</option>
        </select>
        {hasFilters && (
          <button
            onClick={clearFilters}
            className="flex items-center gap-1 text-xs text-slate-400 hover:text-slate-200 transition-colors"
          >
            <X className="h-3 w-3" />
            Clear
          </button>
        )}
        {data && (
          <span className="ml-auto text-xs text-slate-500 tabular-nums">
            {data.total.toLocaleString()} total
          </span>
        )}
      </div>

      <DataTable
        columns={columns}
        data={data?.items ?? []}
        keyFn={(s) => s.id}
        page={page}
        pages={data?.pages ?? 1}
        onPageChange={setPage}
        isLoading={isLoading}
      />
    </div>
  )
}
