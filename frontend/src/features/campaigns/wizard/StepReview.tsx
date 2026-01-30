import { CheckCircle2, AlertCircle } from 'lucide-react'

import { cn } from '@/lib/utils'
import type { WizardFormData } from '../CampaignWizard'
import type { AdAccountResponse } from '@/lib/api'

const objectiveLabels: Record<string, string> = {
  awareness: 'Brand Awareness',
  traffic: 'Website Traffic',
  engagement: 'Engagement',
  leads: 'Lead Generation',
  sales: 'Sales',
  app_promotion: 'App Promotion',
}

interface StepReviewProps {
  formData: WizardFormData
  accounts: AdAccountResponse[]
}

export function StepReview({ formData, accounts }: StepReviewProps) {
  const account = accounts.find((a) => a.id === formData.ad_account_id)
  const validAdCopies = formData.ad_copies.filter(
    (c) => c.headline_1 && c.description_1 && c.final_url
  )

  const Section = ({
    title,
    children,
  }: {
    title: string
    children: React.ReactNode
  }) => (
    <div className="space-y-3">
      <h4 className="font-medium text-sm text-muted-foreground">{title}</h4>
      {children}
    </div>
  )

  const Row = ({
    label,
    value,
    warning,
  }: {
    label: string
    value: React.ReactNode
    warning?: boolean
  }) => (
    <div className="flex justify-between py-2 border-b last:border-0">
      <span className="text-muted-foreground">{label}</span>
      <span className={cn('font-medium', warning && 'text-yellow-600')}>{value}</span>
    </div>
  )

  return (
    <div className="space-y-6">
      <div className="p-4 rounded-lg bg-green-50 border border-green-200 flex items-start gap-3">
        <CheckCircle2 className="h-5 w-5 text-green-600 mt-0.5" />
        <div>
          <p className="font-medium text-green-900">Ready to create your campaign</p>
          <p className="text-sm text-green-700">
            Review the details below before creating. You can edit this campaign anytime
            while it's in draft status.
          </p>
        </div>
      </div>

      {/* Basic Info */}
      <Section title="Basic Information">
        <div className="rounded-lg border p-4">
          <Row label="Campaign Name" value={formData.name} />
          {formData.description && (
            <Row label="Description" value={formData.description} />
          )}
          <Row
            label="Ad Account"
            value={
              account ? (
                <span className="flex items-center gap-2">
                  <span
                    className={cn(
                      'h-5 w-5 rounded text-white text-xs flex items-center justify-center',
                      account.platform === 'google' && 'bg-blue-500',
                      account.platform === 'meta' && 'bg-blue-600',
                      account.platform === 'tiktok' && 'bg-black'
                    )}
                  >
                    {account.platform.charAt(0).toUpperCase()}
                  </span>
                  {account.platform_account_name || account.platform_account_id}
                </span>
              ) : (
                'Not selected'
              )
            }
          />
          <Row label="Objective" value={objectiveLabels[formData.objective] || formData.objective} />
        </div>
      </Section>

      {/* Budget & Schedule */}
      <Section title="Budget & Schedule">
        <div className="rounded-lg border p-4">
          <Row
            label="Budget Type"
            value={formData.budget_type === 'daily' ? 'Daily Budget' : 'Lifetime Budget'}
          />
          <Row
            label={formData.budget_type === 'daily' ? 'Daily Amount' : 'Total Amount'}
            value={`${formData.budget_currency} ${formData.budget_amount.toFixed(2)}`}
          />
          <Row
            label="Start Date"
            value={formData.start_date || 'Start immediately after approval'}
          />
          <Row
            label="End Date"
            value={
              formData.is_ongoing ? (
                <span className="flex items-center gap-1">
                  Ongoing
                  <AlertCircle className="h-4 w-4 text-yellow-500" />
                </span>
              ) : (
                formData.end_date || 'Not set'
              )
            }
            warning={formData.is_ongoing}
          />
        </div>
      </Section>

      {/* Targeting */}
      <Section title="Targeting">
        <div className="rounded-lg border p-4">
          <Row
            label="Locations"
            value={formData.targeting.locations.join(', ') || 'None'}
          />
          <Row
            label="Age Range"
            value={`${formData.targeting.age_min} - ${formData.targeting.age_max}`}
          />
          <Row
            label="Gender"
            value={
              <span className="capitalize">
                {formData.targeting.genders.join(', ')}
              </span>
            }
          />
          {formData.targeting.keywords.length > 0 && (
            <Row
              label="Keywords"
              value={
                <span className="text-right max-w-[200px] truncate">
                  {formData.targeting.keywords.join(', ')}
                </span>
              }
            />
          )}
          {formData.targeting.interests.length > 0 && (
            <Row
              label="Interests"
              value={
                <span className="text-right max-w-[200px] truncate">
                  {formData.targeting.interests.join(', ')}
                </span>
              }
            />
          )}
        </div>
      </Section>

      {/* Ad Copies */}
      <Section title={`Ad Copies (${validAdCopies.length})`}>
        <div className="space-y-3">
          {validAdCopies.map((adCopy, index) => (
            <div key={index} className="rounded-lg border p-4">
              <div className="flex items-center gap-2 mb-3">
                <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-muted">
                  {adCopy.is_primary ? 'Primary' : `Variation ${index}`}
                </span>
              </div>
              <div className="space-y-1">
                <p className="text-primary font-medium">
                  {adCopy.headline_1}
                  {adCopy.headline_2 && ` | ${adCopy.headline_2}`}
                  {adCopy.headline_3 && ` | ${adCopy.headline_3}`}
                </p>
                <p className="text-sm text-green-700 truncate">
                  {adCopy.final_url}
                </p>
                <p className="text-sm text-muted-foreground">
                  {adCopy.description_1}
                  {adCopy.description_2 && ` ${adCopy.description_2}`}
                </p>
              </div>
            </div>
          ))}
          {validAdCopies.length === 0 && (
            <div className="p-4 rounded-lg border border-dashed text-center text-muted-foreground">
              No ad copies configured. Campaign will be created as a draft.
            </div>
          )}
        </div>
      </Section>

      {/* Warnings */}
      {(formData.is_ongoing || validAdCopies.length === 0) && (
        <div className="p-4 rounded-lg bg-yellow-50 border border-yellow-200">
          <div className="flex items-start gap-3">
            <AlertCircle className="h-5 w-5 text-yellow-600 mt-0.5" />
            <div className="text-sm">
              <p className="font-medium text-yellow-900">Things to note</p>
              <ul className="list-disc list-inside text-yellow-700 mt-1 space-y-1">
                {formData.is_ongoing && (
                  <li>Campaign has no end date and will run until manually paused</li>
                )}
                {validAdCopies.length === 0 && (
                  <li>No ad copies configured - you'll need to add them before submitting for approval</li>
                )}
              </ul>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
