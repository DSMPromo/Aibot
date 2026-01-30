import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { cn } from '@/lib/utils'
import type { WizardFormData } from '../CampaignWizard'

interface StepBudgetProps {
  formData: WizardFormData
  errors: Record<string, string>
  updateFormData: (updates: Partial<WizardFormData>) => void
}

export function StepBudget({
  formData,
  errors,
  updateFormData,
}: StepBudgetProps) {
  return (
    <div className="space-y-6">
      {/* Budget Type */}
      <div className="space-y-2">
        <Label>Budget Type</Label>
        <div className="flex gap-4">
          <label
            className={cn(
              'flex-1 flex flex-col p-4 rounded-lg border cursor-pointer transition-colors',
              formData.budget_type === 'daily'
                ? 'border-primary bg-primary/5'
                : 'hover:bg-muted'
            )}
          >
            <input
              type="radio"
              name="budget_type"
              value="daily"
              checked={formData.budget_type === 'daily'}
              onChange={() => updateFormData({ budget_type: 'daily' })}
              className="sr-only"
            />
            <span className="font-medium">Daily Budget</span>
            <span className="text-xs text-muted-foreground">
              Spend up to this amount each day
            </span>
          </label>

          <label
            className={cn(
              'flex-1 flex flex-col p-4 rounded-lg border cursor-pointer transition-colors',
              formData.budget_type === 'lifetime'
                ? 'border-primary bg-primary/5'
                : 'hover:bg-muted'
            )}
          >
            <input
              type="radio"
              name="budget_type"
              value="lifetime"
              checked={formData.budget_type === 'lifetime'}
              onChange={() => updateFormData({ budget_type: 'lifetime' })}
              className="sr-only"
            />
            <span className="font-medium">Lifetime Budget</span>
            <span className="text-xs text-muted-foreground">
              Total spend over campaign duration
            </span>
          </label>
        </div>
      </div>

      {/* Budget Amount */}
      <div className="space-y-2">
        <Label htmlFor="budget_amount">
          {formData.budget_type === 'daily' ? 'Daily Budget' : 'Total Budget'}{' '}
          <span className="text-destructive">*</span>
        </Label>
        <div className="flex items-center gap-2">
          <select
            value={formData.budget_currency}
            onChange={(e) => updateFormData({ budget_currency: e.target.value })}
            className="h-10 rounded-md border border-input bg-background px-3 py-2 text-sm"
          >
            <option value="USD">USD</option>
            <option value="EUR">EUR</option>
            <option value="GBP">GBP</option>
          </select>
          <Input
            id="budget_amount"
            type="number"
            min="1"
            step="0.01"
            value={formData.budget_amount}
            onChange={(e) => updateFormData({ budget_amount: parseFloat(e.target.value) || 0 })}
            className={cn('flex-1', errors.budget_amount && 'border-destructive')}
          />
        </div>
        {errors.budget_amount && (
          <p className="text-sm text-destructive">{errors.budget_amount}</p>
        )}
        <p className="text-xs text-muted-foreground">
          {formData.budget_type === 'daily'
            ? 'This is the maximum you\'ll spend per day. Actual spend may be lower.'
            : 'This is the total amount that will be spent over the campaign lifetime.'}
        </p>
      </div>

      {/* Schedule */}
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            id="is_ongoing"
            checked={formData.is_ongoing}
            onChange={(e) => updateFormData({ is_ongoing: e.target.checked })}
            className="h-4 w-4 rounded border-gray-300"
          />
          <Label htmlFor="is_ongoing" className="font-normal">
            Run continuously (no end date)
          </Label>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="start_date">Start Date</Label>
            <Input
              id="start_date"
              type="date"
              value={formData.start_date}
              onChange={(e) => updateFormData({ start_date: e.target.value })}
              min={new Date().toISOString().split('T')[0]}
            />
            <p className="text-xs text-muted-foreground">
              Leave empty to start immediately after approval
            </p>
          </div>

          {!formData.is_ongoing && (
            <div className="space-y-2">
              <Label htmlFor="end_date">End Date</Label>
              <Input
                id="end_date"
                type="date"
                value={formData.end_date}
                onChange={(e) => updateFormData({ end_date: e.target.value })}
                min={formData.start_date || new Date().toISOString().split('T')[0]}
                className={cn(errors.end_date && 'border-destructive')}
              />
              {errors.end_date && (
                <p className="text-sm text-destructive">{errors.end_date}</p>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Estimated Spend Summary */}
      <div className="p-4 rounded-lg bg-muted">
        <h4 className="font-medium mb-2">Estimated Spend</h4>
        <div className="space-y-1 text-sm">
          <div className="flex justify-between">
            <span className="text-muted-foreground">
              {formData.budget_type === 'daily' ? 'Daily maximum' : 'Total budget'}
            </span>
            <span className="font-medium">
              {formData.budget_currency} {formData.budget_amount.toFixed(2)}
            </span>
          </div>
          {formData.budget_type === 'daily' && !formData.is_ongoing && formData.end_date && formData.start_date && (
            <div className="flex justify-between">
              <span className="text-muted-foreground">Campaign total (estimated)</span>
              <span className="font-medium">
                {formData.budget_currency}{' '}
                {(formData.budget_amount *
                  Math.ceil(
                    (new Date(formData.end_date).getTime() - new Date(formData.start_date).getTime()) /
                      (1000 * 60 * 60 * 24)
                  )).toFixed(2)}
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
