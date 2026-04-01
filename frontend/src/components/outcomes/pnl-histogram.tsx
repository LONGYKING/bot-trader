"use client"

import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, ReferenceLine } from "recharts"
import type { Outcome } from "@/lib/types"

interface PnlHistogramProps {
  data: Outcome[]
}

export function PnlHistogram({ data }: PnlHistogramProps) {
  const sorted = [...data]
    .filter((o) => o.pnl_pct != null)
    .map((o) => ({
      id: o.id.slice(0, 6),
      pnl: (o.pnl_pct! * 100),
    }))
    .sort((a, b) => a.pnl - b.pnl)

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900 p-5">
      <h3 className="mb-4 text-sm font-semibold text-slate-100">Individual PnL</h3>
      {sorted.length === 0 ? (
        <div className="flex h-48 items-center justify-center text-sm text-slate-500">No data</div>
      ) : (
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={sorted} margin={{ top: 4, right: 4, bottom: 0, left: -24 }}>
            <XAxis dataKey="id" tick={false} axisLine={false} tickLine={false} />
            <YAxis
              tick={{ fontSize: 10, fill: "#64748b" }}
              axisLine={false}
              tickLine={false}
              tickFormatter={(v) => `${v > 0 ? "+" : ""}${v.toFixed(0)}%`}
            />
            <Tooltip
              contentStyle={{ background: "#0f172a", border: "1px solid #1e293b", borderRadius: 8, fontSize: 12 }}
              formatter={(v) => { const n = Number(v); return [`${n >= 0 ? "+" : ""}${n.toFixed(2)}%`, "PnL"] }}
              labelStyle={{ color: "#94a3b8" }}
            />
            <ReferenceLine y={0} stroke="#334155" strokeDasharray="3 3" />
            <Bar dataKey="pnl" radius={[2, 2, 0, 0]}>
              {sorted.map((entry) => (
                <Cell key={entry.id} fill={entry.pnl >= 0 ? "#10b981" : "#f43f5e"} fillOpacity={0.8} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}
