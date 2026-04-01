"use client"

import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { outcomes } from "@/lib/api"
import { WinRateDonut } from "@/components/outcomes/win-rate-donut"
import { PnlHistogram } from "@/components/outcomes/pnl-histogram"
import { DataTable } from "@/components/shared/data-table"
import { fmtDate, fmtPct, pnlColor } from "@/lib/utils"
import type { Outcome } from "@/lib/types"
import { BarChart2 } from "lucide-react"
import { EmptyState } from "@/components/shared/empty-state"

export default function OutcomesPage() {
  const [page, setPage] = useState(1)
  const [filter, setFilter] = useState<boolean | undefined>(undefined)

  const { data: stats } = useQuery({
    queryKey: ["outcomes", "stats"],
    queryFn: () => outcomes.stats(),
  })

  const { data, isLoading } = useQuery({
    queryKey: ["outcomes", "list", { page, filter }],
    queryFn: () => outcomes.list({ page, page_size: 25, is_profitable: filter }),
  })

  const columns = [
    {
      key: "pnl",
      header: "PnL",
      render: (o: Outcome) => (
        <span className={`font-semibold tabular-nums ${pnlColor(o.pnl_pct)}`}>
          {fmtPct(o.pnl_pct)}
        </span>
      ),
    },
    {
      key: "result",
      header: "Result",
      render: (o: Outcome) => o.is_profitable == null
        ? <span className="text-slate-500">Pending</span>
        : o.is_profitable
          ? <span className="text-emerald-400">Win</span>
          : <span className="text-rose-400">Loss</span>,
    },
    {
      key: "exit_price",
      header: "Exit Price",
      render: (o: Outcome) => (
        <span className="tabular-nums">{o.exit_price?.toFixed(4) ?? "—"}</span>
      ),
    },
    {
      key: "exit_time",
      header: "Exit Time",
      render: (o: Outcome) => (
        <span className="text-xs text-slate-500 tabular-nums">
          {o.exit_time ? fmtDate(o.exit_time) : "—"}
        </span>
      ),
    },
    {
      key: "computed_at",
      header: "Computed",
      render: (o: Outcome) => (
        <span className="text-xs text-slate-500 tabular-nums">{fmtDate(o.computed_at)}</span>
      ),
    },
  ]

  return (
    <div className="space-y-6">
      {stats && stats.total_count > 0 && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <WinRateDonut stats={stats} />
          <PnlHistogram data={data?.items ?? []} />
        </div>
      )}

      <div>
        <div className="mb-4 flex items-center gap-2">
          {[
            { label: "All", value: undefined },
            { label: "Wins", value: true },
            { label: "Losses", value: false },
          ].map(({ label, value }) => (
            <button
              key={label}
              onClick={() => { setFilter(value); setPage(1) }}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                filter === value
                  ? "bg-slate-800 text-slate-100"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              {label}
            </button>
          ))}
          {data && (
            <span className="ml-auto text-xs text-slate-500 tabular-nums">
              {data.total.toLocaleString()} outcomes
            </span>
          )}
        </div>

        {!isLoading && !data?.items.length ? (
          <EmptyState icon={BarChart2} title="No outcomes yet" />
        ) : (
          <DataTable
            columns={columns}
            data={data?.items ?? []}
            keyFn={(o) => o.id}
            page={page}
            pages={data?.pages ?? 1}
            onPageChange={setPage}
            isLoading={isLoading}
          />
        )}
      </div>
    </div>
  )
}
