"use client"

import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { backtests, strategies } from "@/lib/api"
import { toast } from "sonner"
import { X } from "lucide-react"

interface SubmitBacktestDialogProps {
  open: boolean
  onClose: () => void
}

export function SubmitBacktestDialog({ open, onClose }: SubmitBacktestDialogProps) {
  const qc = useQueryClient()
  const [form, setForm] = useState({
    strategy_id: "",
    date_from: "",
    date_to: "",
    initial_capital: 10000,
  })

  const { data: strategyList } = useQuery({
    queryKey: ["strategies", "all"],
    queryFn: () => strategies.list({ page_size: 100 }),
  })

  const submit = useMutation({
    mutationFn: () => backtests.submit({
      ...form,
      initial_capital: Number(form.initial_capital),
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["backtests"] })
      toast.success("Backtest queued")
      onClose()
    },
    onError: (e: Error) => toast.error(e.message),
  })

  if (!open) return null

  const set = (k: string, v: string | number) => setForm((f) => ({ ...f, [k]: v }))

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-2xl border border-slate-700 bg-slate-900 p-6 shadow-2xl">
        <div className="mb-5 flex items-center justify-between">
          <h2 className="text-base font-semibold text-slate-100">Run Backtest</h2>
          <button onClick={onClose} className="text-slate-500 hover:text-slate-300">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="space-y-4">
          <div>
            <label className="mb-1 block text-xs text-slate-400">Strategy</label>
            <select
              value={form.strategy_id}
              onChange={(e) => set("strategy_id", e.target.value)}
              className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-100 outline-none focus:border-emerald-500"
            >
              <option value="">Select strategy…</option>
              {(strategyList?.items ?? []).map((s) => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="mb-1 block text-xs text-slate-400">From</label>
              <input
                type="date"
                value={form.date_from}
                onChange={(e) => set("date_from", e.target.value)}
                className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-100 outline-none focus:border-emerald-500"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-slate-400">To</label>
              <input
                type="date"
                value={form.date_to}
                onChange={(e) => set("date_to", e.target.value)}
                className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-100 outline-none focus:border-emerald-500"
              />
            </div>
          </div>

          <div>
            <label className="mb-1 block text-xs text-slate-400">Initial Capital (USD)</label>
            <input
              type="number"
              value={form.initial_capital}
              onChange={(e) => set("initial_capital", e.target.value)}
              className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-100 outline-none focus:border-emerald-500"
            />
          </div>
        </div>

        <div className="mt-5 flex gap-3">
          <button
            onClick={() => submit.mutate()}
            disabled={submit.isPending || !form.strategy_id || !form.date_from || !form.date_to}
            className="flex-1 rounded-lg bg-emerald-500 py-2.5 text-sm font-semibold text-slate-950 hover:bg-emerald-400 disabled:opacity-50 transition-colors"
          >
            {submit.isPending ? "Submitting…" : "Run Backtest"}
          </button>
          <button
            onClick={onClose}
            className="flex-1 rounded-lg border border-slate-700 py-2.5 text-sm font-semibold text-slate-300 hover:bg-slate-800 transition-colors"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  )
}
