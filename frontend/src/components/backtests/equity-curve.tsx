"use client"

import { useQuery } from "@tanstack/react-query"
import { backtests } from "@/lib/api"
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from "recharts"
import { fmtDateShort } from "@/lib/utils"

interface EquityCurveProps {
  backtestId: string
  initialCapital: number
}

export function EquityCurve({ backtestId, initialCapital }: EquityCurveProps) {
  const { data, isLoading } = useQuery({
    queryKey: ["backtest-trades", backtestId],
    queryFn: () => backtests.trades(backtestId, { page_size: 500 }),
  })

  if (isLoading) {
    return <div className="h-48 animate-pulse rounded-lg bg-slate-800/50" />
  }

  const trades = data?.items ?? []
  if (!trades.length) return <p className="text-sm text-slate-500">No trades</p>

  // Build equity curve from capital_after
  const chartData = trades.map((t) => ({
    time: fmtDateShort(t.exit_time),
    capital: t.capital_after ?? initialCapital,
  }))

  const minCapital = Math.min(...chartData.map((d) => d.capital))
  const maxCapital = Math.max(...chartData.map((d) => d.capital))

  return (
    <ResponsiveContainer width="100%" height={200}>
      <LineChart data={chartData} margin={{ top: 4, right: 4, bottom: 0, left: -8 }}>
        <XAxis
          dataKey="time"
          tick={{ fontSize: 10, fill: "#64748b" }}
          axisLine={false}
          tickLine={false}
          interval="preserveStartEnd"
        />
        <YAxis
          domain={[minCapital * 0.99, maxCapital * 1.01]}
          tick={{ fontSize: 10, fill: "#64748b" }}
          axisLine={false}
          tickLine={false}
          tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
        />
        <Tooltip
          contentStyle={{ background: "#0f172a", border: "1px solid #1e293b", borderRadius: 8, fontSize: 12 }}
          formatter={(v) => [`$${Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 })}`, "Capital"]}
          labelStyle={{ color: "#94a3b8" }}
        />
        <ReferenceLine y={initialCapital} stroke="#334155" strokeDasharray="3 3" />
        <Line
          type="monotone"
          dataKey="capital"
          stroke="#10b981"
          strokeWidth={2}
          dot={false}
          activeDot={{ r: 4, fill: "#10b981" }}
        />
      </LineChart>
    </ResponsiveContainer>
  )
}
