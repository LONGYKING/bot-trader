"use client"

import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { strategies } from "@/lib/api"
import { toast } from "sonner"
import { X } from "lucide-react"

interface CreateStrategyDialogProps {
  open: boolean
  onClose: () => void
}

export function CreateStrategyDialog({ open, onClose }: CreateStrategyDialogProps) {
  const qc = useQueryClient()
  const [form, setForm] = useState({
    name: "",
    strategy_class: "",
    asset: "",
    timeframe: "1h",
    exchange: "binance",
    trade_type: "spot",
    interval_minutes: 60,
    description: "",
  })

  const { data: classes } = useQuery({
    queryKey: ["strategy-classes"],
    queryFn: () => strategies.classes(),
  })

  const create = useMutation({
    mutationFn: () => strategies.create({
      ...form,
      interval_minutes: Number(form.interval_minutes),
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["strategies"] })
      toast.success("Strategy created")
      onClose()
    },
    onError: (e: Error) => toast.error(e.message),
  })

  if (!open) return null

  const set = (k: string, v: string | number) => setForm((f) => ({ ...f, [k]: v }))

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="w-full max-w-lg rounded-2xl border border-slate-700 bg-slate-900 p-6 shadow-2xl">
        <div className="mb-5 flex items-center justify-between">
          <h2 className="text-base font-semibold text-slate-100">New Strategy</h2>
          <button onClick={onClose} className="text-slate-500 hover:text-slate-300">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="col-span-2">
            <label className="mb-1 block text-xs text-slate-400">Name</label>
            <input
              value={form.name}
              onChange={(e) => set("name", e.target.value)}
              className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-100 outline-none focus:border-emerald-500"
              placeholder="My Strategy"
            />
          </div>

          <div className="col-span-2">
            <label className="mb-1 block text-xs text-slate-400">Strategy Class</label>
            <select
              value={form.strategy_class}
              onChange={(e) => set("strategy_class", e.target.value)}
              className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-100 outline-none focus:border-emerald-500"
            >
              <option value="">Select class…</option>
              {classes?.map((c) => (
                <option key={c.name} value={c.name}>{c.name}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="mb-1 block text-xs text-slate-400">Asset</label>
            <input
              value={form.asset}
              onChange={(e) => set("asset", e.target.value)}
              className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-100 outline-none focus:border-emerald-500"
              placeholder="BTC/USDT"
            />
          </div>

          <div>
            <label className="mb-1 block text-xs text-slate-400">Timeframe</label>
            <select
              value={form.timeframe}
              onChange={(e) => set("timeframe", e.target.value)}
              className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-100 outline-none focus:border-emerald-500"
            >
              {["1m","5m","15m","30m","1h","4h","1d"].map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="mb-1 block text-xs text-slate-400">Exchange</label>
            <input
              value={form.exchange}
              onChange={(e) => set("exchange", e.target.value)}
              className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-100 outline-none focus:border-emerald-500"
              placeholder="binance"
            />
          </div>

          <div>
            <label className="mb-1 block text-xs text-slate-400">Trade Type</label>
            <select
              value={form.trade_type}
              onChange={(e) => set("trade_type", e.target.value)}
              className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-100 outline-none focus:border-emerald-500"
            >
              {["spot", "futures", "options"].map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </div>

          <div className="col-span-2">
            <label className="mb-1 block text-xs text-slate-400">Interval (minutes)</label>
            <input
              type="number"
              value={form.interval_minutes}
              onChange={(e) => set("interval_minutes", e.target.value)}
              className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-100 outline-none focus:border-emerald-500"
            />
          </div>
        </div>

        <div className="mt-5 flex gap-3">
          <button
            onClick={() => create.mutate()}
            disabled={create.isPending || !form.name || !form.strategy_class || !form.asset}
            className="flex-1 rounded-lg bg-emerald-500 py-2.5 text-sm font-semibold text-slate-950 hover:bg-emerald-400 disabled:opacity-50 transition-colors"
          >
            {create.isPending ? "Creating…" : "Create Strategy"}
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
