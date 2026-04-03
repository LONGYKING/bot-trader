"use client"

import Link from "next/link"
import { AlertTriangle } from "lucide-react"

interface UpgradeBannerProps {
  resource: string
  current: number
  limit: number
}

export function UpgradeBanner({ resource, current, limit }: UpgradeBannerProps) {
  return (
    <div className="flex items-center gap-3 rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm">
      <AlertTriangle className="h-4 w-4 shrink-0 text-amber-400" />
      <span className="text-amber-300">
        You&apos;ve reached your {resource} limit ({current}/{limit}).{" "}
        <Link href="/pricing" className="font-semibold underline hover:text-amber-200">
          Upgrade your plan
        </Link>{" "}
        to create more.
      </span>
    </div>
  )
}
