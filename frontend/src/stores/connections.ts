import { create } from 'zustand'
import { connectionsApi, AdAccountResponse, PlatformAccountOption } from '@/lib/api'

interface ConnectionsState {
  accounts: AdAccountResponse[]
  isLoading: boolean
  error: string | null
  pendingOAuth: {
    platform: string
    state: string
  } | null

  // Actions
  fetchConnections: () => Promise<void>
  initiateConnection: (platform: 'google' | 'meta' | 'tiktok') => Promise<string>
  disconnectAccount: (accountId: string) => Promise<void>
  triggerSync: (accountId: string) => Promise<void>
  refreshToken: (accountId: string) => Promise<void>
  clearError: () => void
  setPendingOAuth: (pending: { platform: string; state: string } | null) => void
}

export const useConnectionsStore = create<ConnectionsState>((set, get) => ({
  accounts: [],
  isLoading: false,
  error: null,
  pendingOAuth: null,

  fetchConnections: async () => {
    set({ isLoading: true, error: null })
    try {
      const response = await connectionsApi.listConnections()
      set({ accounts: response.accounts, isLoading: false })
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to fetch connections',
        isLoading: false,
      })
    }
  },

  initiateConnection: async (platform) => {
    set({ isLoading: true, error: null })
    try {
      const response = await connectionsApi.initiateConnection(platform)
      set({
        pendingOAuth: { platform, state: response.state },
        isLoading: false,
      })
      return response.authorization_url
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to initiate connection',
        isLoading: false,
      })
      throw error
    }
  },

  disconnectAccount: async (accountId) => {
    set({ isLoading: true, error: null })
    try {
      await connectionsApi.disconnectAccount(accountId)
      const accounts = get().accounts.filter((a) => a.id !== accountId)
      set({ accounts, isLoading: false })
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to disconnect account',
        isLoading: false,
      })
      throw error
    }
  },

  triggerSync: async (accountId) => {
    set({ error: null })
    try {
      await connectionsApi.triggerSync(accountId)
      // Update the account's sync status
      const accounts = get().accounts.map((a) =>
        a.id === accountId ? { ...a, sync_status: 'syncing' as const } : a
      )
      set({ accounts })
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to trigger sync',
      })
      throw error
    }
  },

  refreshToken: async (accountId) => {
    set({ error: null })
    try {
      await connectionsApi.refreshToken(accountId)
      // Refetch to get updated status
      await get().fetchConnections()
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to refresh token',
      })
      throw error
    }
  },

  clearError: () => set({ error: null }),

  setPendingOAuth: (pending) => set({ pendingOAuth: pending }),
}))
