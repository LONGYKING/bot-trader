"use client"

import { useAuthStore } from "@/hooks/use-auth"
import { useEffect } from "react"
import { useRouter, usePathname } from "next/navigation"

// Pages that don't require authentication and render full-screen (no sidebar)
const AUTH_PAGES = ["/login", "/register"]
// Pages that are public but use the app shell
const PUBLIC_APP_PAGES = ["/pricing"]

export function AuthGate({ children }: { children: React.ReactNode }) {
  const accessToken = useAuthStore((s) => s.accessToken)
  const router = useRouter()
  const pathname = usePathname()

  const isAuthPage = AUTH_PAGES.some((p) => pathname.startsWith(p))

  useEffect(() => {
    if (!accessToken && !isAuthPage && !PUBLIC_APP_PAGES.some((p) => pathname.startsWith(p))) {
      router.replace("/login")
    }
  }, [accessToken, isAuthPage, pathname, router])

  // Auth pages (login/register) render as full-screen — no sidebar/header
  if (isAuthPage) return <>{children}</>

  // Protected / public-app pages — wait for auth check
  if (!accessToken && !PUBLIC_APP_PAGES.some((p) => pathname.startsWith(p))) return null

  return <>{children}</>
}
