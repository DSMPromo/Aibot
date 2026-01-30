import { create } from 'zustand'
import {
  campaignsApi,
  CampaignResponse,
  CampaignCreateRequest,
  CampaignUpdateRequest,
} from '@/lib/api'

interface CampaignsState {
  campaigns: CampaignResponse[]
  currentCampaign: CampaignResponse | null
  isLoading: boolean
  error: string | null
  total: number
  page: number
  pageSize: number
  filters: {
    status?: string
    platform?: string
    search?: string
  }

  // Actions
  fetchCampaigns: (filters?: {
    status_filter?: string
    platform_filter?: string
    search?: string
    page?: number
    page_size?: number
  }) => Promise<void>
  fetchCampaign: (campaignId: string) => Promise<CampaignResponse | null>
  createCampaign: (data: CampaignCreateRequest) => Promise<CampaignResponse>
  updateCampaign: (campaignId: string, data: CampaignUpdateRequest) => Promise<CampaignResponse>
  deleteCampaign: (campaignId: string) => Promise<void>
  submitForApproval: (campaignId: string, comment?: string) => Promise<CampaignResponse>
  approveCampaign: (campaignId: string, comment?: string) => Promise<CampaignResponse>
  rejectCampaign: (campaignId: string, comment: string) => Promise<CampaignResponse>
  pauseCampaign: (campaignId: string) => Promise<CampaignResponse>
  resumeCampaign: (campaignId: string) => Promise<CampaignResponse>
  duplicateCampaign: (campaignId: string) => Promise<CampaignResponse>
  bulkAction: (campaignIds: string[], action: 'pause' | 'resume' | 'archive') => Promise<{ success: number; failed: number }>
  syncCampaign: (campaignId: string) => Promise<CampaignResponse>
  pushCampaign: (campaignId: string) => Promise<CampaignResponse>
  importCsv: (csvContent: string) => Promise<{ created: number; failed: number; campaignIds: string[] }>
  setFilters: (filters: { status?: string; platform?: string; search?: string }) => void
  setPage: (page: number) => void
  clearError: () => void
  clearCurrentCampaign: () => void
}

export const useCampaignsStore = create<CampaignsState>((set, get) => ({
  campaigns: [],
  currentCampaign: null,
  isLoading: false,
  error: null,
  total: 0,
  page: 1,
  pageSize: 20,
  filters: {},

  fetchCampaigns: async (filters) => {
    set({ isLoading: true, error: null })
    try {
      const response = await campaignsApi.listCampaigns({
        ...get().filters,
        ...filters,
        page: filters?.page || get().page,
        page_size: filters?.page_size || get().pageSize,
      })
      set({
        campaigns: response.campaigns,
        total: response.total,
        page: response.page,
        pageSize: response.page_size,
        isLoading: false,
      })
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to fetch campaigns',
        isLoading: false,
      })
    }
  },

  fetchCampaign: async (campaignId) => {
    set({ isLoading: true, error: null })
    try {
      const campaign = await campaignsApi.getCampaign(campaignId)
      set({ currentCampaign: campaign, isLoading: false })
      return campaign
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to fetch campaign',
        isLoading: false,
      })
      return null
    }
  },

  createCampaign: async (data) => {
    set({ isLoading: true, error: null })
    try {
      const campaign = await campaignsApi.createCampaign(data)
      set((state) => ({
        campaigns: [campaign, ...state.campaigns],
        currentCampaign: campaign,
        isLoading: false,
      }))
      return campaign
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to create campaign',
        isLoading: false,
      })
      throw error
    }
  },

  updateCampaign: async (campaignId, data) => {
    set({ isLoading: true, error: null })
    try {
      const campaign = await campaignsApi.updateCampaign(campaignId, data)
      set((state) => ({
        campaigns: state.campaigns.map((c) => (c.id === campaignId ? campaign : c)),
        currentCampaign: state.currentCampaign?.id === campaignId ? campaign : state.currentCampaign,
        isLoading: false,
      }))
      return campaign
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to update campaign',
        isLoading: false,
      })
      throw error
    }
  },

  deleteCampaign: async (campaignId) => {
    set({ isLoading: true, error: null })
    try {
      await campaignsApi.deleteCampaign(campaignId)
      set((state) => ({
        campaigns: state.campaigns.filter((c) => c.id !== campaignId),
        currentCampaign: state.currentCampaign?.id === campaignId ? null : state.currentCampaign,
        isLoading: false,
      }))
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to delete campaign',
        isLoading: false,
      })
      throw error
    }
  },

  submitForApproval: async (campaignId, comment) => {
    set({ error: null })
    try {
      const campaign = await campaignsApi.submitForApproval(campaignId, comment)
      set((state) => ({
        campaigns: state.campaigns.map((c) => (c.id === campaignId ? campaign : c)),
        currentCampaign: state.currentCampaign?.id === campaignId ? campaign : state.currentCampaign,
      }))
      return campaign
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to submit campaign',
      })
      throw error
    }
  },

  approveCampaign: async (campaignId, comment) => {
    set({ error: null })
    try {
      const campaign = await campaignsApi.approveCampaign(campaignId, comment)
      set((state) => ({
        campaigns: state.campaigns.map((c) => (c.id === campaignId ? campaign : c)),
        currentCampaign: state.currentCampaign?.id === campaignId ? campaign : state.currentCampaign,
      }))
      return campaign
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to approve campaign',
      })
      throw error
    }
  },

  rejectCampaign: async (campaignId, comment) => {
    set({ error: null })
    try {
      const campaign = await campaignsApi.rejectCampaign(campaignId, comment)
      set((state) => ({
        campaigns: state.campaigns.map((c) => (c.id === campaignId ? campaign : c)),
        currentCampaign: state.currentCampaign?.id === campaignId ? campaign : state.currentCampaign,
      }))
      return campaign
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to reject campaign',
      })
      throw error
    }
  },

  pauseCampaign: async (campaignId) => {
    set({ error: null })
    try {
      const campaign = await campaignsApi.pauseCampaign(campaignId)
      set((state) => ({
        campaigns: state.campaigns.map((c) => (c.id === campaignId ? campaign : c)),
        currentCampaign: state.currentCampaign?.id === campaignId ? campaign : state.currentCampaign,
      }))
      return campaign
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to pause campaign',
      })
      throw error
    }
  },

  resumeCampaign: async (campaignId) => {
    set({ error: null })
    try {
      const campaign = await campaignsApi.resumeCampaign(campaignId)
      set((state) => ({
        campaigns: state.campaigns.map((c) => (c.id === campaignId ? campaign : c)),
        currentCampaign: state.currentCampaign?.id === campaignId ? campaign : state.currentCampaign,
      }))
      return campaign
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to resume campaign',
      })
      throw error
    }
  },

  duplicateCampaign: async (campaignId) => {
    set({ isLoading: true, error: null })
    try {
      const campaign = await campaignsApi.duplicateCampaign(campaignId)
      set((state) => ({
        campaigns: [campaign, ...state.campaigns],
        isLoading: false,
      }))
      return campaign
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to duplicate campaign',
        isLoading: false,
      })
      throw error
    }
  },

  bulkAction: async (campaignIds, action) => {
    set({ error: null })
    try {
      const result = await campaignsApi.bulkAction(campaignIds, action)
      // Refresh campaigns after bulk action
      await get().fetchCampaigns()
      return { success: result.success_count, failed: result.failure_count }
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to perform bulk action',
      })
      throw error
    }
  },

  syncCampaign: async (campaignId) => {
    set({ error: null })
    try {
      const campaign = await campaignsApi.syncCampaign(campaignId)
      set((state) => ({
        campaigns: state.campaigns.map((c) => (c.id === campaignId ? campaign : c)),
        currentCampaign: state.currentCampaign?.id === campaignId ? campaign : state.currentCampaign,
      }))
      return campaign
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to sync campaign',
      })
      throw error
    }
  },

  pushCampaign: async (campaignId) => {
    set({ error: null })
    try {
      const campaign = await campaignsApi.pushCampaign(campaignId)
      set((state) => ({
        campaigns: state.campaigns.map((c) => (c.id === campaignId ? campaign : c)),
        currentCampaign: state.currentCampaign?.id === campaignId ? campaign : state.currentCampaign,
      }))
      return campaign
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to push campaign to platform',
      })
      throw error
    }
  },

  importCsv: async (csvContent) => {
    set({ isLoading: true, error: null })
    try {
      const result = await campaignsApi.importCsv(csvContent)
      // Refresh campaigns after import
      await get().fetchCampaigns()
      set({ isLoading: false })
      return {
        created: result.created_count,
        failed: result.error_count,
        campaignIds: result.campaign_ids,
      }
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to import CSV',
        isLoading: false,
      })
      throw error
    }
  },

  setFilters: (filters) => {
    set({ filters, page: 1 })
  },

  setPage: (page) => {
    set({ page })
  },

  clearError: () => set({ error: null }),

  clearCurrentCampaign: () => set({ currentCampaign: null }),
}))
