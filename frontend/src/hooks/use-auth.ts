"use client"

import { create } from "zustand"
import { persist } from "zustand/middleware"

export interface AuthLimits {
  max_strategies: number
  max_channels: number
  max_api_keys: number
  max_backtests_per_month: number
  max_signals_per_day: number
  max_signals_per_month: number
  allowed_strategy_classes: string[] | null
  allowed_channel_types: string[] | null
  can_backtest: boolean
  can_create_api_keys: boolean
  can_use_exchange_channels: boolean
}

export interface AuthUser {
  id: string
  email: string
  full_name: string | null
  is_owner: boolean
}

export interface AuthTenant {
  id: string
  name: string
  plan_key: string
  plan_status: string
}

interface AuthState {
  accessToken: string | null
  refreshToken: string | null
  user: AuthUser | null
  tenant: AuthTenant | null
  limits: AuthLimits | null
  setTokens: (access: string, refresh: string) => void
  setProfile: (user: AuthUser, tenant: AuthTenant, limits: AuthLimits) => void
  logout: () => void
  isAuthenticated: () => boolean
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      accessToken: null,
      refreshToken: null,
      user: null,
      tenant: null,
      limits: null,

      setTokens: (access, refresh) =>
        set({ accessToken: access, refreshToken: refresh }),

      setProfile: (user, tenant, limits) =>
        set({ user, tenant, limits }),

      logout: () =>
        set({ accessToken: null, refreshToken: null, user: null, tenant: null, limits: null }),

      isAuthenticated: () => !!get().accessToken,
    }),
    {
      name: "bt_auth",
      partialize: (state) => ({
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
        user: state.user,
        tenant: state.tenant,
        limits: state.limits,
      }),
    }
  )
)
