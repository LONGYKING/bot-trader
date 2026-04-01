"use client"

import { useQuery } from "@tanstack/react-query"
import { outcomes } from "@/lib/api"
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
} from "recharts"
import { fmtPct } from "@/lib/utils"

export function OutcomeChart() {
  const { data, isLoading } = useQuery({
    queryKey: ["outcomes", "list-chart"],
    queryFn: () => outcomes.list({ page_size: 50 }),
  })

  if (isLoading) {
    return (
      <div className="rounded-xl border border-slate-800 bg-slate-900 p-5">
        <div className="mb-4 h-4 w-32 animate-pulse rounded bg-slate-800" />
        <div className="h-48 animate-pulse rounded bg-slate-800/50" />
      </div>
    )
  }

  const items = data?.items ?? []

  // Build histogram buckets
  const buckets: Record<string, number> = {
    "<-5%": 0, "-5 to -2%": 0, "-2 to 0%": 0, "0 to 2%": 0, "2 to 5%": 0, ">5%": 0,
  }

  for (const item of items) {
    const v = (item.pnl_pct ?? 0) * 100
    if (v < -5) buckets["<-5%"]++
    else if (v < -2) buckets["-5 to -2%"]++
    else if (v < 0) buckets["-2 to 0%"]++
    else if (v < 2) buckets["0 to 2%"]++
    else if (v < 5) buckets["2 to 5%"]++
    else buckets[">5%"]++
  }

  const chartData = Object.entries(buckets).map(([name, count]) => ({ name, count }))

  const getColor = (name: string) =>
    name.startsWith("<") || name.startsWith("-") ? "#f43f5e" : "#10b981"

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900 p-5">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-100">PnL Distribution</h2>
        <span className="text-xs text-slate-500">{items.length} outcomes</span>
      </div>
      {items.length === 0 ? (
        <div className="flex h-48 items-center justify-center text-sm text-slate-500">
          No outcome data yet
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={180}>
          <BarChart data={chartData} margin={{ top: 4, right: 0, bottom: 0, left: -20 }}>
            <XAxis
              dataKey="name"
              tick={{ fontSize: 10, fill: "#64748b" }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              tick={{ fontSize: 10, fill: "#64748b" }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip
              contentStyle={{ background: "#0f172a", border: "1px solid #1e293b", borderRadius: 8, fontSize: 12 }}
              itemStyle={{ color: "#94a3b8" }}
              labelStyle={{ color: "#e2e8f0" }}
              formatter={(v) => [Number(v), "Count"]}
            />
            <Bar dataKey="count" radius={[4, 4, 0, 0]}>
              {chartData.map((entry) => (
                <Cell key={entry.name} fill={getColor(entry.name)} fillOpacity={0.85} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}
