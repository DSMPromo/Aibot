import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  Plus,
  Search,
  Filter,
  MoreHorizontal,
  Play,
  Pause,
  Copy,
  Trash2,
  CheckCircle2,
  Clock,
  AlertCircle,
  XCircle,
  Archive,
  Loader2,
} from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useCampaignsStore } from '@/stores/campaigns'
import { useToast } from '@/hooks/use-toast'
import { cn } from '@/lib/utils'
import type { CampaignResponse } from '@/lib/api'

const statusConfig: Record<
  CampaignResponse['status'],
  { label: string; color: string; icon: React.ComponentType<{ className?: string }> }
> = {
  draft: { label: 'Draft', color: 'bg-gray-100 text-gray-700', icon: Clock },
  pending_review: { label: 'Pending Review', color: 'bg-yellow-100 text-yellow-700', icon: Clock },
  approved: { label: 'Approved', color: 'bg-blue-100 text-blue-700', icon: CheckCircle2 },
  rejected: { label: 'Rejected', color: 'bg-red-100 text-red-700', icon: XCircle },
  active: { label: 'Active', color: 'bg-green-100 text-green-700', icon: Play },
  paused: { label: 'Paused', color: 'bg-orange-100 text-orange-700', icon: Pause },
  archived: { label: 'Archived', color: 'bg-gray-100 text-gray-500', icon: Archive },
}

const objectiveLabels: Record<string, string> = {
  awareness: 'Awareness',
  traffic: 'Traffic',
  engagement: 'Engagement',
  leads: 'Leads',
  sales: 'Sales',
  app_promotion: 'App Promotion',
}

function StatusBadge({ status }: { status: CampaignResponse['status'] }) {
  const config = statusConfig[status]
  const Icon = config.icon

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium',
        config.color
      )}
    >
      <Icon className="h-3 w-3" />
      {config.label}
    </span>
  )
}

function CampaignCard({
  campaign,
  onPause,
  onResume,
  onDuplicate,
  onDelete,
}: {
  campaign: CampaignResponse
  onPause: () => void
  onResume: () => void
  onDuplicate: () => void
  onDelete: () => void
}) {
  const [menuOpen, setMenuOpen] = useState(false)

  return (
    <Card className="hover:shadow-md transition-shadow">
      <CardContent className="p-4">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0 flex-1">
            <Link
              to={`/campaigns/${campaign.id}`}
              className="font-medium hover:text-primary truncate block"
            >
              {campaign.name}
            </Link>
            <div className="flex items-center gap-2 mt-1">
              <StatusBadge status={campaign.status} />
              <span
                className={cn(
                  'h-5 w-5 rounded text-white text-xs flex items-center justify-center font-medium',
                  campaign.platform === 'google' && 'bg-blue-500',
                  campaign.platform === 'meta' && 'bg-blue-600',
                  campaign.platform === 'tiktok' && 'bg-black'
                )}
              >
                {campaign.platform.charAt(0).toUpperCase()}
              </span>
              <span className="text-xs text-muted-foreground">
                {objectiveLabels[campaign.objective]}
              </span>
            </div>
          </div>

          <div className="relative">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setMenuOpen(!menuOpen)}
            >
              <MoreHorizontal className="h-4 w-4" />
            </Button>

            {menuOpen && (
              <>
                <div
                  className="fixed inset-0"
                  onClick={() => setMenuOpen(false)}
                />
                <div className="absolute right-0 top-full mt-1 w-48 rounded-lg border bg-white shadow-lg z-10">
                  <div className="p-1">
                    <Link
                      to={`/campaigns/${campaign.id}`}
                      className="flex items-center gap-2 w-full px-3 py-2 text-sm rounded-md hover:bg-muted"
                    >
                      View Details
                    </Link>
                    {campaign.status === 'active' && (
                      <button
                        onClick={() => {
                          setMenuOpen(false)
                          onPause()
                        }}
                        className="flex items-center gap-2 w-full px-3 py-2 text-sm rounded-md hover:bg-muted"
                      >
                        <Pause className="h-4 w-4" />
                        Pause
                      </button>
                    )}
                    {campaign.status === 'paused' && (
                      <button
                        onClick={() => {
                          setMenuOpen(false)
                          onResume()
                        }}
                        className="flex items-center gap-2 w-full px-3 py-2 text-sm rounded-md hover:bg-muted"
                      >
                        <Play className="h-4 w-4" />
                        Resume
                      </button>
                    )}
                    <button
                      onClick={() => {
                        setMenuOpen(false)
                        onDuplicate()
                      }}
                      className="flex items-center gap-2 w-full px-3 py-2 text-sm rounded-md hover:bg-muted"
                    >
                      <Copy className="h-4 w-4" />
                      Duplicate
                    </button>
                    <button
                      onClick={() => {
                        setMenuOpen(false)
                        onDelete()
                      }}
                      className="flex items-center gap-2 w-full px-3 py-2 text-sm rounded-md hover:bg-muted text-destructive"
                    >
                      <Trash2 className="h-4 w-4" />
                      Delete
                    </button>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>

        <div className="mt-4 pt-4 border-t grid grid-cols-3 gap-4 text-sm">
          <div>
            <p className="text-muted-foreground">Budget</p>
            <p className="font-medium">
              {campaign.budget_currency} {campaign.budget_amount.toFixed(2)}
              <span className="text-muted-foreground font-normal">
                /{campaign.budget_type === 'daily' ? 'day' : 'total'}
              </span>
            </p>
          </div>
          <div>
            <p className="text-muted-foreground">Start</p>
            <p className="font-medium">
              {campaign.start_date
                ? new Date(campaign.start_date).toLocaleDateString()
                : 'Immediate'}
            </p>
          </div>
          <div>
            <p className="text-muted-foreground">End</p>
            <p className="font-medium">
              {campaign.is_ongoing
                ? 'Ongoing'
                : campaign.end_date
                ? new Date(campaign.end_date).toLocaleDateString()
                : '-'}
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

export default function CampaignsListPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const { toast } = useToast()

  const {
    campaigns,
    total,
    page,
    isLoading,
    fetchCampaigns,
    pauseCampaign,
    resumeCampaign,
    duplicateCampaign,
    deleteCampaign,
    setFilters,
    setPage,
  } = useCampaignsStore()

  const [search, setSearch] = useState(searchParams.get('search') || '')
  const [statusFilter, setStatusFilter] = useState(searchParams.get('status') || '')
  const [platformFilter, setPlatformFilter] = useState(searchParams.get('platform') || '')

  useEffect(() => {
    fetchCampaigns({
      search: search || undefined,
      status_filter: statusFilter || undefined,
      platform_filter: platformFilter || undefined,
    })
  }, [fetchCampaigns, search, statusFilter, platformFilter])

  const handleSearch = (value: string) => {
    setSearch(value)
    setSearchParams((prev) => {
      if (value) prev.set('search', value)
      else prev.delete('search')
      return prev
    })
  }

  const handlePause = async (id: string) => {
    try {
      await pauseCampaign(id)
      toast({ title: 'Campaign paused' })
    } catch {
      toast({ title: 'Error', description: 'Failed to pause campaign', variant: 'destructive' })
    }
  }

  const handleResume = async (id: string) => {
    try {
      await resumeCampaign(id)
      toast({ title: 'Campaign resumed' })
    } catch {
      toast({ title: 'Error', description: 'Failed to resume campaign', variant: 'destructive' })
    }
  }

  const handleDuplicate = async (id: string) => {
    try {
      await duplicateCampaign(id)
      toast({ title: 'Campaign duplicated' })
    } catch {
      toast({ title: 'Error', description: 'Failed to duplicate campaign', variant: 'destructive' })
    }
  }

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to delete this campaign?')) return
    try {
      await deleteCampaign(id)
      toast({ title: 'Campaign deleted' })
    } catch {
      toast({ title: 'Error', description: 'Failed to delete campaign', variant: 'destructive' })
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Campaigns</h1>
          <p className="text-muted-foreground">Manage your advertising campaigns</p>
        </div>
        <Button asChild>
          <Link to="/campaigns/new">
            <Plus className="h-4 w-4 mr-2" />
            Create Campaign
          </Link>
        </Button>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search campaigns..."
            value={search}
            onChange={(e) => handleSearch(e.target.value)}
            className="pl-9"
          />
        </div>

        <select
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value)
            setSearchParams((prev) => {
              if (e.target.value) prev.set('status', e.target.value)
              else prev.delete('status')
              return prev
            })
          }}
          className="h-10 rounded-md border border-input bg-background px-3 py-2 text-sm min-w-[140px]"
        >
          <option value="">All Statuses</option>
          <option value="draft">Draft</option>
          <option value="pending_review">Pending Review</option>
          <option value="approved">Approved</option>
          <option value="active">Active</option>
          <option value="paused">Paused</option>
          <option value="rejected">Rejected</option>
          <option value="archived">Archived</option>
        </select>

        <select
          value={platformFilter}
          onChange={(e) => {
            setPlatformFilter(e.target.value)
            setSearchParams((prev) => {
              if (e.target.value) prev.set('platform', e.target.value)
              else prev.delete('platform')
              return prev
            })
          }}
          className="h-10 rounded-md border border-input bg-background px-3 py-2 text-sm min-w-[140px]"
        >
          <option value="">All Platforms</option>
          <option value="google">Google Ads</option>
          <option value="meta">Meta Ads</option>
          <option value="tiktok">TikTok Ads</option>
        </select>
      </div>

      {/* Campaign List */}
      {isLoading && campaigns.length === 0 ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      ) : campaigns.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <div className="mx-auto w-12 h-12 rounded-full bg-muted flex items-center justify-center mb-4">
              <AlertCircle className="h-6 w-6 text-muted-foreground" />
            </div>
            <h3 className="font-medium mb-1">No campaigns found</h3>
            <p className="text-sm text-muted-foreground mb-4">
              {search || statusFilter || platformFilter
                ? 'Try adjusting your filters'
                : 'Get started by creating your first campaign'}
            </p>
            {!search && !statusFilter && !platformFilter && (
              <Button asChild>
                <Link to="/campaigns/new">
                  <Plus className="h-4 w-4 mr-2" />
                  Create Campaign
                </Link>
              </Button>
            )}
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {campaigns.map((campaign) => (
            <CampaignCard
              key={campaign.id}
              campaign={campaign}
              onPause={() => handlePause(campaign.id)}
              onResume={() => handleResume(campaign.id)}
              onDuplicate={() => handleDuplicate(campaign.id)}
              onDelete={() => handleDelete(campaign.id)}
            />
          ))}
        </div>
      )}

      {/* Pagination */}
      {total > 20 && (
        <div className="flex items-center justify-center gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={page === 1}
            onClick={() => {
              setPage(page - 1)
              fetchCampaigns({ page: page - 1 })
            }}
          >
            Previous
          </Button>
          <span className="text-sm text-muted-foreground">
            Page {page} of {Math.ceil(total / 20)}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= Math.ceil(total / 20)}
            onClick={() => {
              setPage(page + 1)
              fetchCampaigns({ page: page + 1 })
            }}
          >
            Next
          </Button>
        </div>
      )}
    </div>
  )
}
