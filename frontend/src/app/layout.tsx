import type { Metadata } from "next"
import { Geist, Geist_Mono } from "next/font/google"
import "./globals.css"
import { Providers } from "@/providers/providers"
import { AuthGate } from "@/components/layout/auth-gate"
import { Sidebar } from "@/components/layout/sidebar"
import { Header } from "@/components/layout/header"

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
})

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
})

export const metadata: Metadata = {
  title: "BotTrader",
  description: "Algorithmic trading signal platform",
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable}`}>
      <body>
        <Providers>
          <AuthGate>
            <Sidebar />
            <Header />
            <main className="ml-56 pt-14 min-h-screen">
              <div className="p-6">
                {children}
              </div>
            </main>
          </AuthGate>
        </Providers>
      </body>
    </html>
  )
}
