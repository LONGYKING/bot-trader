"use client"

import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { backtests } from "@/lib/api"
import { SubmitBacktestDialog } from "@/components/backtests/submit-backtest-dialog"
import { EquityCurve } from "@/components/backtests/equity-curve"
import { backtestStatusBadge, fmtDate, fmtPct } from "@/lib/utils"
import { EmptyState } from "@/components/shared/empty-state"
import { FlaskConical, Plus, ChevronDown, ChevronRight } from "lucide-react"
import { cn } from "@/lib/utils"

export default function BacktestsPage() {
  const [showCreate, setShowCreate] = useState(false)
  const [expanded, setExpanded] = useState<string | null>(null)
  const [page, setPage] = useState(1)

  const { data, isLoading } = useQuery({
    queryKey: ["backtests", page],
    queryFn: () => backtests.list({ page, page_size: 20 }),
  })

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <p className="text-xs text-slate-500">{data?.total ?? 0} backtests</p>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-1.5 rounded-lg bg-emerald-500 px-3 py-2 text-xs font-semibold text-slate-950 hover:bg-emerald-400 transition-colors"
        >
          <Plus className="h-3.5 w-3.5" />
          Run Backtest
        </button>
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-16 animate-pulse rounded-xl bg-slate-800" />
          ))}
        </div>
      ) : !data?.items.length ? (
        <EmptyState
          icon={FlaskConical}
          title="No backtests yet"
          description="Run a backtest to evaluate your strategy historically"
          action={
            <button
              onClick={() => setShowCreate(true)}
              className="rounded-lg bg-emerald-500 px-4 py-2 text-sm font-semibold text-slate-950 hover:bg-emerald-400 transition-colors"
            >
              Run Backtest
            </button>
          }
        />
      ) : (
        <div className="space-y-2">
          {data.items.map((bt) => (
            <div key={bt.id} className="rounded-xl border border-slate-800 bg-slate-900 overflow-hidden">
              <button
                onClick={() => setExpanded(expanded === bt.id ? null : bt.id)}
                className="flex w-full items-center gap-4 px-5 py-4 text-left hover:bg-slate-800/30 transition-colors"
              >
                <span className={cn("rounded px-2 py-0.5 text-xs font-semibold", backtestStatusBadge(bt.status))}>
                  {bt.status}
                </span>
                <span className="text-sm font-medium text-slate-200 flex-1">
                  {bt.date_from.slice(0, 10)} → {bt.date_to.slice(0, 10)}
                </span>
                {bt.win_rate != null && (
                  <span className="text-xs text-slate-400 tabular-nums">
                    WR: {(bt.win_rate * 100).toFixed(1)}%
                  </span>
                )}
                {bt.total_pnl_pct != null && (
                  <span className={`text-xs font-semibold tabular-nums ${bt.total_pnl_pct >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                    {fmtPct(bt.total_pnl_pct)}
                  </span>
                )}
                <span className="text-xs text-slate-500">{fmtDate(bt.created_at)}</span>
                {expanded === bt.id
                  ? <ChevronDown className="h-3.5 w-3.5 text-slate-500 shrink-0" />
                  : <ChevronRight className="h-3.5 w-3.5 text-slate-500 shrink-0" />
                }
              </button>

              {expanded === bt.id && (
                <div className="border-t border-slate-800 px-5 py-4 space-y-4">
                  <div className="grid grid-cols-3 gap-4 text-sm sm:grid-cols-6">
                    {[
                      ["Trades", bt.total_trades ?? "—"],
                      ["Wins", bt.winning_trades ?? "—"],
                      ["Win Rate", bt.win_rate != null ? `${(bt.win_rate * 100).toFixed(1)}%` : "—"],
                      ["Total PnL", bt.total_pnl_pct != null ? fmtPct(bt.total_pnl_pct) : "—"],
                      ["Sharpe", bt.sharpe_ratio?.toFixed(2) ?? "—"],
                      ["Max DD", bt.max_drawdown_pct != null ? fmtPct(bt.max_drawdown_pct) : "—"],
                    ].map(([k, v]) => (
                      <div key={k}>
                        <p className="text-xs text-slate-500">{k}</p>
                        <p className="text-sm font-semibold text-slate-200 tabular-nums">{v}</p>
                      </div>
                    ))}
                  </div>

                  {bt.status === "completed" && (
                    <EquityCurve backtestId={bt.id} initialCapital={bt.initial_capital} />
                  )}

                  {bt.error_message && (
                    <p className="text-xs text-rose-400">{bt.error_message}</p>
                  )}
                </div>
              )}
            </div>
          ))}

          {data.pages > 1 && (
            <div className="flex justify-center gap-3 pt-2">
              <button
                onClick={() => setPage((p) => p - 1)}
                disabled={page <= 1}
                className="text-xs text-slate-400 hover:text-slate-200 disabled:opacity-40"
              >
                Prev
              </button>
              <span className="text-xs text-slate-500">{page} / {data.pages}</span>
              <button
                onClick={() => setPage((p) => p + 1)}
                disabled={page >= data.pages}
                className="text-xs text-slate-400 hover:text-slate-200 disabled:opacity-40"
              >
                Next
              </button>
            </div>
          )}
        </div>
      )}

      <SubmitBacktestDialog open={showCreate} onClose={() => setShowCreate(false)} />
    </div>
  )
}
