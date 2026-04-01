"use client"

import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { channels } from "@/lib/api"
import { ChannelCard } from "@/components/channels/channel-card"
import { CreateChannelDialog } from "@/components/channels/create-channel-dialog"
import { DeliveryDrawer } from "@/components/channels/delivery-drawer"
import { EmptyState } from "@/components/shared/empty-state"
import { Radio, Plus } from "lucide-react"

export default function ChannelsPage() {
  const [showCreate, setShowCreate] = useState(false)
  const [drawerChannelId, setDrawerChannelId] = useState<string | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ["channels"],
    queryFn: () => channels.list({ page_size: 100 }),
  })

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <p className="text-xs text-slate-500">{data?.length ?? 0} channels</p>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-1.5 rounded-lg bg-emerald-500 px-3 py-2 text-xs font-semibold text-slate-950 hover:bg-emerald-400 transition-colors"
        >
          <Plus className="h-3.5 w-3.5" />
          New Channel
        </button>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-36 animate-pulse rounded-xl bg-slate-800" />
          ))}
        </div>
      ) : !data?.length ? (
        <EmptyState
          icon={Radio}
          title="No channels"
          description="Add a channel to start receiving signals"
          action={
            <button
              onClick={() => setShowCreate(true)}
              className="rounded-lg bg-emerald-500 px-4 py-2 text-sm font-semibold text-slate-950 hover:bg-emerald-400 transition-colors"
            >
              Add Channel
            </button>
          }
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {data.map((c) => (
            <ChannelCard
              key={c.id}
              channel={c}
              onViewDeliveries={setDrawerChannelId}
            />
          ))}
        </div>
      )}

      <CreateChannelDialog open={showCreate} onClose={() => setShowCreate(false)} />
      <DeliveryDrawer channelId={drawerChannelId} onClose={() => setDrawerChannelId(null)} />
    </div>
  )
}
