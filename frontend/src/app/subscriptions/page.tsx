"use client"

import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { subscriptions, channels, strategies } from "@/lib/api"
import { DataTable } from "@/components/shared/data-table"
import { StatusDot } from "@/components/shared/status-dot"
import { EmptyState } from "@/components/shared/empty-state"
import { fmtDate } from "@/lib/utils"
import type { Subscription } from "@/lib/types"
import { toast } from "sonner"
import { Link2, Plus, X } from "lucide-react"

export default function SubscriptionsPage() {
  const [page, setPage] = useState(1)
  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState({ channel_id: "", strategy_id: "" })

  const qc = useQueryClient()

  const { data, isLoading } = useQuery({
    queryKey: ["subscriptions", page],
    queryFn: () => subscriptions.list({ page, page_size: 25 }),
  })

  const { data: channelList } = useQuery({
    queryKey: ["channels"],
    queryFn: () => channels.list({ page_size: 100 }),
  })

  const { data: strategyList } = useQuery({
    queryKey: ["strategies", "all"],
    queryFn: () => strategies.list({ page_size: 100 }),
  })

  const create = useMutation({
    mutationFn: () => subscriptions.create({
      channel_id: form.channel_id,
      strategy_id: form.strategy_id || null,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["subscriptions"] })
      toast.success("Subscription created")
      setShowCreate(false)
      setForm({ channel_id: "", strategy_id: "" })
    },
    onError: (e: Error) => toast.error(e.message),
  })

  const toggle = useMutation({
    mutationFn: ({ id, active }: { id: string; active: boolean }) =>
      subscriptions.update(id, { is_active: active }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["subscriptions"] })
      toast.success("Updated")
    },
    onError: (e: Error) => toast.error(e.message),
  })

  const remove = useMutation({
    mutationFn: (id: string) => subscriptions.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["subscriptions"] })
      toast.success("Deleted")
    },
    onError: (e: Error) => toast.error(e.message),
  })

  const channelMap = Object.fromEntries((channelList ?? []).map((c) => [c.id, c.name]))
  const strategyMap = Object.fromEntries((strategyList?.items ?? []).map((s) => [s.id, s.name]))

  const columns = [
    {
      key: "channel",
      header: "Channel",
      render: (s: Subscription) => (
        <span className="font-medium text-slate-200">{channelMap[s.channel_id] ?? s.channel_id.slice(0, 8)}</span>
      ),
    },
    {
      key: "strategy",
      header: "Strategy",
      render: (s: Subscription) => s.strategy_id
        ? <span>{strategyMap[s.strategy_id] ?? s.strategy_id.slice(0, 8)}</span>
        : <span className="text-slate-500">All</span>,
    },
    {
      key: "filters",
      header: "Filters",
      render: (s: Subscription) => {
        const parts: string[] = []
        if (s.asset_filter?.length) parts.push(s.asset_filter.join(", "))
        if (s.signal_filter?.length) parts.push(`signals: ${s.signal_filter.join(", ")}`)
        if (s.min_confidence > 0) parts.push(`conf ≥ ${Math.round(s.min_confidence * 100)}%`)
        return parts.length
          ? <span className="text-xs text-slate-400">{parts.join(" · ")}</span>
          : <span className="text-xs text-slate-600">None</span>
      },
    },
    {
      key: "status",
      header: "Status",
      render: (s: Subscription) => (
        <StatusDot status={s.is_active ? "active" : "inactive"} label={s.is_active ? "Active" : "Inactive"} />
      ),
    },
    {
      key: "created",
      header: "Created",
      render: (s: Subscription) => (
        <span className="text-xs text-slate-500 tabular-nums">{fmtDate(s.created_at)}</span>
      ),
    },
    {
      key: "actions",
      header: "",
      render: (s: Subscription) => (
        <div className="flex items-center gap-2">
          <button
            onClick={() => toggle.mutate({ id: s.id, active: !s.is_active })}
            className="text-xs text-slate-400 hover:text-slate-200 transition-colors"
          >
            {s.is_active ? "Pause" : "Resume"}
          </button>
          <button
            onClick={() => { if (confirm("Delete?")) remove.mutate(s.id) }}
            className="text-xs text-rose-400 hover:text-rose-300 transition-colors"
          >
            Delete
          </button>
        </div>
      ),
    },
  ]

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <p className="text-xs text-slate-500">{data?.total ?? 0} subscriptions</p>
        <button
          onClick={() => setShowCreate((v) => !v)}
          className="flex items-center gap-1.5 rounded-lg bg-emerald-500 px-3 py-2 text-xs font-semibold text-slate-950 hover:bg-emerald-400 transition-colors"
        >
          <Plus className="h-3.5 w-3.5" />
          New
        </button>
      </div>

      {showCreate && (
        <div className="rounded-xl border border-slate-700 bg-slate-900 p-5">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-100">New Subscription</h3>
            <button onClick={() => setShowCreate(false)} className="text-slate-500 hover:text-slate-300">
              <X className="h-4 w-4" />
            </button>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="mb-1 block text-xs text-slate-400">Channel</label>
              <select
                value={form.channel_id}
                onChange={(e) => setForm((f) => ({ ...f, channel_id: e.target.value }))}
                className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-100 outline-none focus:border-emerald-500"
              >
                <option value="">Select channel…</option>
                {(channelList ?? []).map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs text-slate-400">Strategy (optional)</label>
              <select
                value={form.strategy_id}
                onChange={(e) => setForm((f) => ({ ...f, strategy_id: e.target.value }))}
                className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-100 outline-none focus:border-emerald-500"
              >
                <option value="">All strategies</option>
                {(strategyList?.items ?? []).map((s) => (
                  <option key={s.id} value={s.id}>{s.name}</option>
                ))}
              </select>
            </div>
          </div>
          <button
            onClick={() => create.mutate()}
            disabled={create.isPending || !form.channel_id}
            className="mt-4 rounded-lg bg-emerald-500 px-4 py-2 text-sm font-semibold text-slate-950 hover:bg-emerald-400 disabled:opacity-50 transition-colors"
          >
            {create.isPending ? "Creating…" : "Create"}
          </button>
        </div>
      )}

      {!isLoading && !data?.items.length ? (
        <EmptyState
          icon={Link2}
          title="No subscriptions"
          description="Link a channel to a strategy to receive signals"
        />
      ) : (
        <DataTable
          columns={columns}
          data={data?.items ?? []}
          keyFn={(s) => s.id}
          page={page}
          pages={data?.pages ?? 1}
          onPageChange={setPage}
          isLoading={isLoading}
        />
      )}
    </div>
  )
}
