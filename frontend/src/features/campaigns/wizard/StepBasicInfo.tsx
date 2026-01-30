import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { cn } from '@/lib/utils'
import type { WizardFormData } from '../CampaignWizard'
import type { AdAccountResponse } from '@/lib/api'

const objectives = [
  { id: 'awareness', label: 'Brand Awareness', description: 'Increase visibility and reach' },
  { id: 'traffic', label: 'Website Traffic', description: 'Drive visitors to your website' },
  { id: 'engagement', label: 'Engagement', description: 'Get more likes, comments, shares' },
  { id: 'leads', label: 'Lead Generation', description: 'Collect leads and contact info' },
  { id: 'sales', label: 'Sales', description: 'Drive purchases and conversions' },
  { id: 'app_promotion', label: 'App Promotion', description: 'Increase app installs' },
]

interface StepBasicInfoProps {
  formData: WizardFormData
  errors: Record<string, string>
  accounts: AdAccountResponse[]
  updateFormData: (updates: Partial<WizardFormData>) => void
}

export function StepBasicInfo({
  formData,
  errors,
  accounts,
  updateFormData,
}: StepBasicInfoProps) {
  return (
    <div className="space-y-6">
      {/* Campaign Name */}
      <div className="space-y-2">
        <Label htmlFor="name">
          Campaign Name <span className="text-destructive">*</span>
        </Label>
        <Input
          id="name"
          value={formData.name}
          onChange={(e) => updateFormData({ name: e.target.value })}
          placeholder="e.g., Summer Sale 2024"
          className={cn(errors.name && 'border-destructive')}
        />
        {errors.name && (
          <p className="text-sm text-destructive">{errors.name}</p>
        )}
      </div>

      {/* Description */}
      <div className="space-y-2">
        <Label htmlFor="description">Description (optional)</Label>
        <textarea
          id="description"
          value={formData.description}
          onChange={(e) => updateFormData({ description: e.target.value })}
          placeholder="Brief description of your campaign goals"
          className="w-full min-h-[80px] px-3 py-2 rounded-md border border-input bg-background text-sm"
        />
      </div>

      {/* Ad Account Selection */}
      <div className="space-y-2">
        <Label>
          Ad Account <span className="text-destructive">*</span>
        </Label>
        {accounts.length === 0 ? (
          <div className="p-4 rounded-lg border border-dashed text-center">
            <p className="text-muted-foreground text-sm">
              No ad accounts connected.{' '}
              <a href="/settings/connections" className="text-primary hover:underline">
                Connect an account
              </a>
            </p>
          </div>
        ) : (
          <div className="grid gap-3">
            {accounts.filter(a => a.is_active).map((account) => (
              <label
                key={account.id}
                className={cn(
                  'flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors',
                  formData.ad_account_id === account.id
                    ? 'border-primary bg-primary/5'
                    : 'hover:bg-muted'
                )}
              >
                <input
                  type="radio"
                  name="ad_account"
                  value={account.id}
                  checked={formData.ad_account_id === account.id}
                  onChange={(e) => updateFormData({ ad_account_id: e.target.value })}
                  className="sr-only"
                />
                <div
                  className={cn(
                    'h-10 w-10 rounded-lg flex items-center justify-center text-white font-bold',
                    account.platform === 'google' && 'bg-blue-500',
                    account.platform === 'meta' && 'bg-blue-600',
                    account.platform === 'tiktok' && 'bg-black'
                  )}
                >
                  {account.platform.charAt(0).toUpperCase()}
                </div>
                <div className="flex-1">
                  <p className="font-medium">
                    {account.platform_account_name || account.platform_account_id}
                  </p>
                  <p className="text-xs text-muted-foreground capitalize">
                    {account.platform} Ads
                  </p>
                </div>
                <div
                  className={cn(
                    'h-5 w-5 rounded-full border-2 flex items-center justify-center',
                    formData.ad_account_id === account.id
                      ? 'border-primary'
                      : 'border-muted-foreground'
                  )}
                >
                  {formData.ad_account_id === account.id && (
                    <div className="h-2.5 w-2.5 rounded-full bg-primary" />
                  )}
                </div>
              </label>
            ))}
          </div>
        )}
        {errors.ad_account_id && (
          <p className="text-sm text-destructive">{errors.ad_account_id}</p>
        )}
      </div>

      {/* Campaign Objective */}
      <div className="space-y-2">
        <Label>
          Campaign Objective <span className="text-destructive">*</span>
        </Label>
        <div className="grid gap-3 sm:grid-cols-2">
          {objectives.map((objective) => (
            <label
              key={objective.id}
              className={cn(
                'flex flex-col p-4 rounded-lg border cursor-pointer transition-colors',
                formData.objective === objective.id
                  ? 'border-primary bg-primary/5'
                  : 'hover:bg-muted'
              )}
            >
              <input
                type="radio"
                name="objective"
                value={objective.id}
                checked={formData.objective === objective.id}
                onChange={(e) => updateFormData({ objective: e.target.value })}
                className="sr-only"
              />
              <span className="font-medium">{objective.label}</span>
              <span className="text-xs text-muted-foreground">
                {objective.description}
              </span>
            </label>
          ))}
        </div>
        {errors.objective && (
          <p className="text-sm text-destructive">{errors.objective}</p>
        )}
      </div>
    </div>
  )
}
