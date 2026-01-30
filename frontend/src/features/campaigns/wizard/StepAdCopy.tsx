import { useState } from 'react'
import { Plus, Trash2, Sparkles } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { cn } from '@/lib/utils'
import type { WizardFormData } from '../CampaignWizard'
import { AIGenerationModal } from './AIGenerationModal'

interface StepAdCopyProps {
  formData: WizardFormData
  errors: Record<string, string>
  updateFormData: (updates: Partial<WizardFormData>) => void
  platform?: string
}

export function StepAdCopy({
  formData,
  errors,
  updateFormData,
  platform = 'google',
}: StepAdCopyProps) {
  const [aiModalOpen, setAiModalOpen] = useState(false)
  const [aiTargetIndex, setAiTargetIndex] = useState(0)

  const updateAdCopy = (index: number, updates: Partial<WizardFormData['ad_copies'][0]>) => {
    const newAdCopies = [...formData.ad_copies]
    newAdCopies[index] = { ...newAdCopies[index], ...updates }
    updateFormData({ ad_copies: newAdCopies })
  }

  const addAdCopy = () => {
    updateFormData({
      ad_copies: [
        ...formData.ad_copies,
        {
          headline_1: '',
          headline_2: '',
          headline_3: '',
          description_1: '',
          description_2: '',
          path_1: '',
          path_2: '',
          final_url: '',
          call_to_action: '',
          is_primary: false,
        },
      ],
    })
  }

  const removeAdCopy = (index: number) => {
    if (formData.ad_copies.length > 1) {
      const newAdCopies = formData.ad_copies.filter((_, i) => i !== index)
      // Ensure at least one is primary
      if (newAdCopies.every((c) => !c.is_primary)) {
        newAdCopies[0].is_primary = true
      }
      updateFormData({ ad_copies: newAdCopies })
    }
  }

  const setPrimary = (index: number) => {
    const newAdCopies = formData.ad_copies.map((copy, i) => ({
      ...copy,
      is_primary: i === index,
    }))
    updateFormData({ ad_copies: newAdCopies })
  }

  const openAiModal = (index: number) => {
    setAiTargetIndex(index)
    setAiModalOpen(true)
  }

  const handleApplyAiVariation = (variation: {
    headline_1: string
    headline_2: string
    headline_3: string
    description_1: string
    description_2: string
    call_to_action: string
  }) => {
    updateAdCopy(aiTargetIndex, {
      headline_1: variation.headline_1,
      headline_2: variation.headline_2,
      headline_3: variation.headline_3,
      description_1: variation.description_1,
      description_2: variation.description_2,
      call_to_action: variation.call_to_action,
    })
  }

  const CharCount = ({ value, max }: { value: string; max: number }) => (
    <span className={cn('text-xs', value.length > max ? 'text-destructive' : 'text-muted-foreground')}>
      {value.length}/{max}
    </span>
  )

  return (
    <div className="space-y-6">
      <p className="text-sm text-muted-foreground">
        Create compelling ad copy for your campaign. You can add multiple variations for A/B testing.
      </p>

      {formData.ad_copies.map((adCopy, index) => (
        <div key={index} className="p-4 rounded-lg border space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <h4 className="font-medium">
                {adCopy.is_primary ? 'Primary Ad Copy' : `Variation ${index}`}
              </h4>
              {!adCopy.is_primary && (
                <button
                  type="button"
                  onClick={() => setPrimary(index)}
                  className="text-xs text-primary hover:underline"
                >
                  Set as primary
                </button>
              )}
            </div>
            <div className="flex items-center gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => openAiModal(index)}
                className="text-primary"
              >
                <Sparkles className="h-4 w-4 mr-1" />
                AI Generate
              </Button>
              {formData.ad_copies.length > 1 && (
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  onClick={() => removeAdCopy(index)}
                  className="text-muted-foreground hover:text-destructive"
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              )}
            </div>
          </div>

          {/* Headlines */}
          <div className="space-y-3">
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label>
                  Headline 1 <span className="text-destructive">*</span>
                </Label>
                <CharCount value={adCopy.headline_1} max={30} />
              </div>
              <Input
                value={adCopy.headline_1}
                onChange={(e) => updateAdCopy(index, { headline_1: e.target.value })}
                placeholder="e.g., Get 50% Off Today"
                maxLength={30}
                className={cn(index === 0 && errors.headline_1 && 'border-destructive')}
              />
              {index === 0 && errors.headline_1 && (
                <p className="text-sm text-destructive">{errors.headline_1}</p>
              )}
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label>Headline 2</Label>
                  <CharCount value={adCopy.headline_2} max={30} />
                </div>
                <Input
                  value={adCopy.headline_2}
                  onChange={(e) => updateAdCopy(index, { headline_2: e.target.value })}
                  placeholder="e.g., Free Shipping"
                  maxLength={30}
                />
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label>Headline 3</Label>
                  <CharCount value={adCopy.headline_3} max={30} />
                </div>
                <Input
                  value={adCopy.headline_3}
                  onChange={(e) => updateAdCopy(index, { headline_3: e.target.value })}
                  placeholder="e.g., Shop Now"
                  maxLength={30}
                />
              </div>
            </div>
          </div>

          {/* Descriptions */}
          <div className="space-y-3">
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label>
                  Description 1 <span className="text-destructive">*</span>
                </Label>
                <CharCount value={adCopy.description_1} max={90} />
              </div>
              <textarea
                value={adCopy.description_1}
                onChange={(e) => updateAdCopy(index, { description_1: e.target.value })}
                placeholder="Describe your offer in detail..."
                maxLength={90}
                className={cn(
                  'w-full min-h-[60px] px-3 py-2 rounded-md border border-input bg-background text-sm',
                  index === 0 && errors.description_1 && 'border-destructive'
                )}
              />
              {index === 0 && errors.description_1 && (
                <p className="text-sm text-destructive">{errors.description_1}</p>
              )}
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label>Description 2</Label>
                <CharCount value={adCopy.description_2} max={90} />
              </div>
              <textarea
                value={adCopy.description_2}
                onChange={(e) => updateAdCopy(index, { description_2: e.target.value })}
                placeholder="Additional details or call to action..."
                maxLength={90}
                className="w-full min-h-[60px] px-3 py-2 rounded-md border border-input bg-background text-sm"
              />
            </div>
          </div>

          {/* URL and Paths */}
          <div className="space-y-3">
            <div className="space-y-2">
              <Label>
                Landing Page URL <span className="text-destructive">*</span>
              </Label>
              <Input
                value={adCopy.final_url}
                onChange={(e) => updateAdCopy(index, { final_url: e.target.value })}
                placeholder="https://example.com/landing-page"
                type="url"
                className={cn(index === 0 && errors.final_url && 'border-destructive')}
              />
              {index === 0 && errors.final_url && (
                <p className="text-sm text-destructive">{errors.final_url}</p>
              )}
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label>Display Path 1</Label>
                  <CharCount value={adCopy.path_1} max={15} />
                </div>
                <Input
                  value={adCopy.path_1}
                  onChange={(e) => updateAdCopy(index, { path_1: e.target.value })}
                  placeholder="e.g., products"
                  maxLength={15}
                />
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label>Display Path 2</Label>
                  <CharCount value={adCopy.path_2} max={15} />
                </div>
                <Input
                  value={adCopy.path_2}
                  onChange={(e) => updateAdCopy(index, { path_2: e.target.value })}
                  placeholder="e.g., sale"
                  maxLength={15}
                />
              </div>
            </div>
            <p className="text-xs text-muted-foreground">
              Display URL: example.com/{adCopy.path_1 || 'path1'}/{adCopy.path_2 || 'path2'}
            </p>
          </div>

          {/* Preview */}
          <div className="p-4 rounded-lg bg-muted">
            <p className="text-xs text-muted-foreground mb-2">Ad Preview</p>
            <div className="space-y-1">
              <p className="text-primary text-lg font-medium">
                {adCopy.headline_1 || 'Headline 1'} | {adCopy.headline_2 || 'Headline 2'} | {adCopy.headline_3 || 'Headline 3'}
              </p>
              <p className="text-sm text-green-700">
                example.com/{adCopy.path_1 || 'path1'}/{adCopy.path_2 || 'path2'}
              </p>
              <p className="text-sm">
                {adCopy.description_1 || 'Description 1'} {adCopy.description_2 || 'Description 2'}
              </p>
            </div>
          </div>
        </div>
      ))}

      {/* Add Variation Button */}
      <Button type="button" variant="outline" onClick={addAdCopy} className="w-full">
        <Plus className="h-4 w-4 mr-2" />
        Add Ad Copy Variation
      </Button>

      <p className="text-xs text-muted-foreground text-center">
        Adding multiple variations helps optimize performance through A/B testing
      </p>

      {/* AI Generation Modal */}
      <AIGenerationModal
        open={aiModalOpen}
        onOpenChange={setAiModalOpen}
        objective={formData.objective}
        platform={platform}
        onApplyVariation={handleApplyAiVariation}
      />
    </div>
  )
}
