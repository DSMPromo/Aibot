import { useEffect, useState } from 'react'
import { Link, useParams, useNavigate } from 'react-router-dom'
import {
  ArrowLeft,
  Play,
  Pause,
  Send,
  CheckCircle,
  XCircle,
  Copy,
  Trash2,
  Edit,
  Loader2,
  ExternalLink,
  RefreshCw,
  Clock,
  Archive,
} from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { useCampaignsStore } from '@/stores/campaigns'
import { useConnectionsStore } from '@/stores/connections'
import { useToast } from '@/hooks/use-toast'
import { cn } from '@/lib/utils'
import type { CampaignResponse } from '@/lib/api'

const statusConfig: Record<
  CampaignResponse['status'],
  { label: string; color: string; bgColor: string; icon: React.ComponentType<{ className?: string }> }
> = {
  draft: { label: 'Draft', color: 'text-gray-700', bgColor: 'bg-gray-100', icon: Edit },
  pending_review: { label: 'Pending Review', color: 'text-yellow-700', bgColor: 'bg-yellow-100', icon: Clock },
  approved: { label: 'Approved', color: 'text-blue-700', bgColor: 'bg-blue-100', icon: CheckCircle },
  rejected: { label: 'Rejected', color: 'text-red-700', bgColor: 'bg-red-100', icon: XCircle },
  active: { label: 'Active', color: 'text-green-700', bgColor: 'bg-green-100', icon: Play },
  paused: { label: 'Paused', color: 'text-orange-700', bgColor: 'bg-orange-100', icon: Pause },
  archived: { label: 'Archived', color: 'text-gray-500', bgColor: 'bg-gray-100', icon: Archive },
}

const objectiveLabels: Record<string, string> = {
  awareness: 'Brand Awareness',
  traffic: 'Website Traffic',
  engagement: 'Engagement',
  leads: 'Lead Generation',
  sales: 'Sales',
  app_promotion: 'App Promotion',
}

export default function CampaignDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { toast } = useToast()
  const { accounts } = useConnectionsStore()

  const {
    currentCampaign: campaign,
    isLoading,
    fetchCampaign,
    submitForApproval,
    approveCampaign,
    rejectCampaign,
    pauseCampaign,
    resumeCampaign,
    duplicateCampaign,
    deleteCampaign,
    clearCurrentCampaign,
  } = useCampaignsStore()

  const [rejectionComment, setRejectionComment] = useState('')
  const [showRejectModal, setShowRejectModal] = useState(false)

  useEffect(() => {
    if (id) {
      fetchCampaign(id)
    }
    return () => clearCurrentCampaign()
  }, [id, fetchCampaign, clearCurrentCampaign])

  if (isLoading || !campaign) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  const account = accounts.find((a) => a.id === campaign.ad_account_id)
  const statusInfo = statusConfig[campaign.status]
  const StatusIcon = statusInfo.icon

  const handleSubmit = async () => {
    try {
      await submitForApproval(campaign.id)
      toast({ title: 'Campaign submitted for approval' })
    } catch {
      toast({ title: 'Error', description: 'Failed to submit campaign', variant: 'destructive' })
    }
  }

  const handleApprove = async () => {
    try {
      await approveCampaign(campaign.id)
      toast({ title: 'Campaign approved' })
    } catch {
      toast({ title: 'Error', description: 'Failed to approve campaign', variant: 'destructive' })
    }
  }

  const handleReject = async () => {
    if (!rejectionComment.trim()) {
      toast({ title: 'Error', description: 'Please provide a rejection reason', variant: 'destructive' })
      return
    }
    try {
      await rejectCampaign(campaign.id, rejectionComment)
      setShowRejectModal(false)
      setRejectionComment('')
      toast({ title: 'Campaign rejected' })
    } catch {
      toast({ title: 'Error', description: 'Failed to reject campaign', variant: 'destructive' })
    }
  }

  const handlePause = async () => {
    try {
      await pauseCampaign(campaign.id)
      toast({ title: 'Campaign paused' })
    } catch {
      toast({ title: 'Error', description: 'Failed to pause campaign', variant: 'destructive' })
    }
  }

  const handleResume = async () => {
    try {
      await resumeCampaign(campaign.id)
      toast({ title: 'Campaign resumed' })
    } catch {
      toast({ title: 'Error', description: 'Failed to resume campaign', variant: 'destructive' })
    }
  }

  const handleDuplicate = async () => {
    try {
      const newCampaign = await duplicateCampaign(campaign.id)
      toast({ title: 'Campaign duplicated' })
      navigate(`/campaigns/${newCampaign.id}`)
    } catch {
      toast({ title: 'Error', description: 'Failed to duplicate campaign', variant: 'destructive' })
    }
  }

  const handleDelete = async () => {
    if (!confirm('Are you sure you want to delete this campaign?')) return
    try {
      await deleteCampaign(campaign.id)
      toast({ title: 'Campaign deleted' })
      navigate('/campaigns')
    } catch {
      toast({ title: 'Error', description: 'Failed to delete campaign', variant: 'destructive' })
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" asChild>
          <Link to="/campaigns">
            <ArrowLeft className="h-5 w-5" />
          </Link>
        </Button>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-semibold">{campaign.name}</h1>
            <span
              className={cn(
                'inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-sm font-medium',
                statusInfo.bgColor,
                statusInfo.color
              )}
            >
              <StatusIcon className="h-4 w-4" />
              {statusInfo.label}
            </span>
          </div>
          {campaign.description && (
            <p className="text-muted-foreground mt-1">{campaign.description}</p>
          )}
        </div>
      </div>

      {/* Actions Bar */}
      <Card>
        <CardContent className="py-4">
          <div className="flex flex-wrap items-center gap-2">
            {campaign.status === 'draft' && (
              <>
                <Button onClick={handleSubmit}>
                  <Send className="h-4 w-4 mr-2" />
                  Submit for Approval
                </Button>
                <Button variant="outline" asChild>
                  <Link to={`/campaigns/${campaign.id}/edit`}>
                    <Edit className="h-4 w-4 mr-2" />
                    Edit
                  </Link>
                </Button>
              </>
            )}

            {campaign.status === 'pending_review' && (
              <>
                <Button onClick={handleApprove}>
                  <CheckCircle className="h-4 w-4 mr-2" />
                  Approve
                </Button>
                <Button variant="outline" onClick={() => setShowRejectModal(true)}>
                  <XCircle className="h-4 w-4 mr-2" />
                  Reject
                </Button>
              </>
            )}

            {campaign.status === 'active' && (
              <Button variant="outline" onClick={handlePause}>
                <Pause className="h-4 w-4 mr-2" />
                Pause
              </Button>
            )}

            {campaign.status === 'paused' && (
              <Button onClick={handleResume}>
                <Play className="h-4 w-4 mr-2" />
                Resume
              </Button>
            )}

            {campaign.status === 'rejected' && (
              <Button variant="outline" asChild>
                <Link to={`/campaigns/${campaign.id}/edit`}>
                  <Edit className="h-4 w-4 mr-2" />
                  Edit & Resubmit
                </Link>
              </Button>
            )}

            <div className="flex-1" />

            <Button variant="outline" onClick={handleDuplicate}>
              <Copy className="h-4 w-4 mr-2" />
              Duplicate
            </Button>

            <Button variant="outline" className="text-destructive" onClick={handleDelete}>
              <Trash2 className="h-4 w-4 mr-2" />
              Delete
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Rejection Reason */}
      {campaign.status === 'rejected' && campaign.status_reason && (
        <Card className="border-red-200 bg-red-50">
          <CardContent className="py-4">
            <div className="flex items-start gap-3">
              <XCircle className="h-5 w-5 text-red-600 mt-0.5" />
              <div>
                <p className="font-medium text-red-900">Rejection Reason</p>
                <p className="text-sm text-red-700">{campaign.status_reason}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Main Info */}
        <div className="lg:col-span-2 space-y-6">
          {/* Campaign Details */}
          <Card>
            <CardHeader>
              <CardTitle>Campaign Details</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <p className="text-sm text-muted-foreground">Platform</p>
                  <div className="flex items-center gap-2 mt-1">
                    <span
                      className={cn(
                        'h-6 w-6 rounded text-white text-xs flex items-center justify-center font-medium',
                        campaign.platform === 'google' && 'bg-blue-500',
                        campaign.platform === 'meta' && 'bg-blue-600',
                        campaign.platform === 'tiktok' && 'bg-black'
                      )}
                    >
                      {campaign.platform.charAt(0).toUpperCase()}
                    </span>
                    <span className="font-medium capitalize">{campaign.platform} Ads</span>
                  </div>
                </div>

                <div>
                  <p className="text-sm text-muted-foreground">Objective</p>
                  <p className="font-medium mt-1">{objectiveLabels[campaign.objective]}</p>
                </div>

                <div>
                  <p className="text-sm text-muted-foreground">Ad Account</p>
                  <p className="font-medium mt-1">
                    {account?.platform_account_name || account?.platform_account_id || 'Unknown'}
                  </p>
                </div>

                <div>
                  <p className="text-sm text-muted-foreground">Version</p>
                  <p className="font-medium mt-1">v{campaign.version}</p>
                </div>
              </div>

              {campaign.platform_campaign_id && (
                <div className="pt-4 border-t">
                  <p className="text-sm text-muted-foreground">Platform Campaign ID</p>
                  <div className="flex items-center gap-2 mt-1">
                    <code className="px-2 py-1 rounded bg-muted text-sm">
                      {campaign.platform_campaign_id}
                    </code>
                    {campaign.last_synced_at && (
                      <span className="text-xs text-muted-foreground">
                        Last synced: {new Date(campaign.last_synced_at).toLocaleString()}
                      </span>
                    )}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Budget & Schedule */}
          <Card>
            <CardHeader>
              <CardTitle>Budget & Schedule</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <p className="text-sm text-muted-foreground">Budget Type</p>
                  <p className="font-medium mt-1 capitalize">{campaign.budget_type}</p>
                </div>

                <div>
                  <p className="text-sm text-muted-foreground">Budget Amount</p>
                  <p className="font-medium mt-1">
                    {campaign.budget_currency} {campaign.budget_amount.toFixed(2)}
                    <span className="text-muted-foreground font-normal">
                      /{campaign.budget_type === 'daily' ? 'day' : 'total'}
                    </span>
                  </p>
                </div>

                <div>
                  <p className="text-sm text-muted-foreground">Start Date</p>
                  <p className="font-medium mt-1">
                    {campaign.start_date
                      ? new Date(campaign.start_date).toLocaleDateString()
                      : 'Starts immediately after approval'}
                  </p>
                </div>

                <div>
                  <p className="text-sm text-muted-foreground">End Date</p>
                  <p className="font-medium mt-1">
                    {campaign.is_ongoing
                      ? 'Ongoing (no end date)'
                      : campaign.end_date
                      ? new Date(campaign.end_date).toLocaleDateString()
                      : 'Not set'}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Ad Copies */}
          <Card>
            <CardHeader>
              <CardTitle>Ad Copies ({campaign.ad_copies.length})</CardTitle>
            </CardHeader>
            <CardContent>
              {campaign.ad_copies.length === 0 ? (
                <p className="text-muted-foreground text-center py-4">
                  No ad copies configured
                </p>
              ) : (
                <div className="space-y-4">
                  {campaign.ad_copies.map((adCopy, index) => (
                    <div key={adCopy.id} className="p-4 rounded-lg border">
                      <div className="flex items-center gap-2 mb-2">
                        <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-muted">
                          {adCopy.is_primary ? 'Primary' : `Variation ${index + 1}`}
                        </span>
                        {adCopy.is_ai_generated && (
                          <span className="text-xs px-2 py-0.5 rounded-full bg-purple-100 text-purple-700">
                            AI Generated
                          </span>
                        )}
                      </div>
                      <p className="text-primary font-medium">
                        {adCopy.headline_1}
                        {adCopy.headline_2 && ` | ${adCopy.headline_2}`}
                        {adCopy.headline_3 && ` | ${adCopy.headline_3}`}
                      </p>
                      <p className="text-sm text-green-700 truncate">{adCopy.final_url}</p>
                      <p className="text-sm text-muted-foreground mt-1">
                        {adCopy.description_1}
                        {adCopy.description_2 && ` ${adCopy.description_2}`}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Targeting */}
          <Card>
            <CardHeader>
              <CardTitle>Targeting</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {campaign.targeting ? (
                <>
                  <div>
                    <p className="text-sm text-muted-foreground">Locations</p>
                    <p className="font-medium">
                      {(campaign.targeting as any).locations?.join(', ') || 'Not set'}
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Age Range</p>
                    <p className="font-medium">
                      {(campaign.targeting as any).age_min || 18} -{' '}
                      {(campaign.targeting as any).age_max || 65}
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Gender</p>
                    <p className="font-medium capitalize">
                      {(campaign.targeting as any).genders?.join(', ') || 'All'}
                    </p>
                  </div>
                </>
              ) : (
                <p className="text-muted-foreground">No targeting configured</p>
              )}
            </CardContent>
          </Card>

          {/* Activity */}
          <Card>
            <CardHeader>
              <CardTitle>Activity</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Created</span>
                <span>{new Date(campaign.created_at).toLocaleDateString()}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Updated</span>
                <span>{new Date(campaign.updated_at).toLocaleDateString()}</span>
              </div>
              {campaign.approved_at && (
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Approved</span>
                  <span>{new Date(campaign.approved_at).toLocaleDateString()}</span>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Rejection Modal */}
      {showRejectModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div
            className="absolute inset-0 bg-black/50"
            onClick={() => setShowRejectModal(false)}
          />
          <Card className="relative w-full max-w-md mx-4">
            <CardHeader>
              <CardTitle>Reject Campaign</CardTitle>
              <CardDescription>
                Provide a reason for rejecting this campaign
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <textarea
                value={rejectionComment}
                onChange={(e) => setRejectionComment(e.target.value)}
                placeholder="Enter rejection reason..."
                className="w-full min-h-[100px] px-3 py-2 rounded-md border border-input bg-background text-sm"
              />
              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={() => setShowRejectModal(false)}>
                  Cancel
                </Button>
                <Button variant="destructive" onClick={handleReject}>
                  Reject Campaign
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  )
}
