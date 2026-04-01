"use client"

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { Toaster } from "sonner"
import { useState } from "react"

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            retry: 1,
          },
        },
      })
  )

  return (
    <QueryClientProvider client={queryClient}>
      {children}
      <Toaster
        theme="dark"
        position="bottom-right"
        toastOptions={{
          classNames: {
            toast: "bg-slate-800 border border-slate-700 text-slate-100",
            error: "bg-rose-950 border-rose-800 text-rose-100",
            success: "bg-emerald-950 border-emerald-800 text-emerald-100",
          },
        }}
      />
    </QueryClientProvider>
  )
}
