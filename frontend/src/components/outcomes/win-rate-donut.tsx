"use client"

import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts"
import type { OutcomeStats } from "@/lib/types"

interface WinRateDonutProps {
  stats: OutcomeStats
}

export function WinRateDonut({ stats }: WinRateDonutProps) {
  const winPct = stats.win_rate * 100
  const lossPct = 100 - winPct

  const data = [
    { name: "Win", value: winPct },
    { name: "Loss", value: lossPct },
  ]

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900 p-5">
      <h3 className="mb-4 text-sm font-semibold text-slate-100">Win Rate</h3>
      <div className="flex items-center gap-6">
        <div className="relative h-32 w-32 shrink-0">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={data}
                cx="50%"
                cy="50%"
                innerRadius={38}
                outerRadius={56}
                dataKey="value"
                strokeWidth={0}
              >
                <Cell fill="#10b981" />
                <Cell fill="#1e293b" />
              </Pie>
              <Tooltip
                contentStyle={{ background: "#0f172a", border: "1px solid #1e293b", borderRadius: 8, fontSize: 12 }}
                formatter={(v) => [`${Number(v).toFixed(1)}%`]}
              />
            </PieChart>
          </ResponsiveContainer>
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="text-xl font-bold text-slate-100">{winPct.toFixed(0)}%</span>
          </div>
        </div>
        <div className="space-y-2">
          <div>
            <p className="text-xs text-slate-500">Total</p>
            <p className="text-lg font-semibold text-slate-100 tabular-nums">{stats.total_count}</p>
          </div>
          <div>
            <p className="text-xs text-slate-500">Winning</p>
            <p className="text-lg font-semibold text-emerald-400 tabular-nums">{stats.winning_count}</p>
          </div>
          <div>
            <p className="text-xs text-slate-500">Avg PnL</p>
            <p className={`text-sm font-semibold tabular-nums ${stats.avg_pnl_pct >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
              {stats.avg_pnl_pct >= 0 ? "+" : ""}{(stats.avg_pnl_pct * 100).toFixed(2)}%
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
