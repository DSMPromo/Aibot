import { useState, useEffect } from 'react'
import { Sparkles, Loader2, AlertTriangle, Check, RefreshCw } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog'
import { cn } from '@/lib/utils'
import {
  aiApi,
  type AIUsageLimits,
  type FullAdCopyVariation,
  type FullAdCopyGenerationRequest,
} from '@/lib/api'

interface AIGenerationModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  objective: string
  platform: string
  onApplyVariation: (variation: {
    headline_1: string
    headline_2: string
    headline_3: string
    description_1: string
    description_2: string
    call_to_action: string
  }) => void
}

export function AIGenerationModal({
  open,
  onOpenChange,
  objective,
  platform,
  onApplyVariation,
}: AIGenerationModalProps) {
  // Form state
  const [product, setProduct] = useState('')
  const [audience, setAudience] = useState('')
  const [benefits, setBenefits] = useState('')
  const [url, setUrl] = useState('')
  const [additionalContext, setAdditionalContext] = useState('')

  // Generation state
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [variations, setVariations] = useState<FullAdCopyVariation[]>([])
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null)

  // Usage limits
  const [usageLimits, setUsageLimits] = useState<AIUsageLimits | null>(null)
  const [loadingLimits, setLoadingLimits] = useState(false)

  // Load usage limits when modal opens
  useEffect(() => {
    if (open) {
      loadUsageLimits()
    }
  }, [open])

  const loadUsageLimits = async () => {
    setLoadingLimits(true)
    try {
      const limits = await aiApi.getUsageLimits()
      setUsageLimits(limits)
    } catch {
      // Silently fail - usage limits are informational
    } finally {
      setLoadingLimits(false)
    }
  }

  const handleGenerate = async () => {
    if (!product || !audience || !benefits || !url) {
      setError('Please fill in all required fields')
      return
    }

    setIsLoading(true)
    setError(null)
    setVariations([])
    setSelectedIndex(null)

    try {
      const request: FullAdCopyGenerationRequest = {
        product,
        audience,
        benefits,
        objective,
        url,
        platform,
        num_variations: 3,
        additional_context: additionalContext || undefined,
      }

      const response = await aiApi.generateFullAdCopy(request)
      setVariations(response.variations)
      // Refresh usage limits after generation
      loadUsageLimits()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate ad copy')
    } finally {
      setIsLoading(false)
    }
  }

  const handleApply = () => {
    if (selectedIndex !== null && variations[selectedIndex]) {
      const variation = variations[selectedIndex]
      onApplyVariation({
        headline_1: variation.headline_1,
        headline_2: variation.headline_2 || '',
        headline_3: variation.headline_3 || '',
        description_1: variation.description_1,
        description_2: variation.description_2 || '',
        call_to_action: variation.cta,
      })
      onOpenChange(false)
      // Reset state
      setVariations([])
      setSelectedIndex(null)
    }
  }

  const handleClose = () => {
    onOpenChange(false)
    setVariations([])
    setSelectedIndex(null)
    setError(null)
  }

  const isFormValid = product && audience && benefits && url

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto" onClose={handleClose}>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-primary" />
            Generate Ad Copy with AI
          </DialogTitle>
          <DialogDescription>
            Describe your product and audience to generate compelling ad copy variations.
          </DialogDescription>
        </DialogHeader>

        {/* Usage Warning */}
        {usageLimits && usageLimits.should_warn && (
          <div className="flex items-center gap-2 p-3 rounded-lg bg-yellow-50 text-yellow-800 dark:bg-yellow-900/20 dark:text-yellow-200">
            <AlertTriangle className="h-4 w-4 flex-shrink-0" />
            <span className="text-sm">
              You've used {usageLimits.usage_percentage.toFixed(0)}% of your monthly AI generations
              ({usageLimits.generations_used}/{usageLimits.generation_limit})
            </span>
          </div>
        )}

        {usageLimits && usageLimits.is_limit_reached && (
          <div className="flex items-center gap-2 p-3 rounded-lg bg-destructive/10 text-destructive">
            <AlertTriangle className="h-4 w-4 flex-shrink-0" />
            <span className="text-sm">
              You've reached your monthly AI generation limit. Upgrade your plan for more generations.
            </span>
          </div>
        )}

        {/* Input Form */}
        {variations.length === 0 && (
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="product">
                Product/Service Description <span className="text-destructive">*</span>
              </Label>
              <textarea
                id="product"
                value={product}
                onChange={(e) => setProduct(e.target.value)}
                placeholder="e.g., Premium online fitness coaching program with personalized workout plans and nutrition guidance"
                className="w-full min-h-[80px] px-3 py-2 rounded-md border border-input bg-background text-sm"
                maxLength={500}
              />
              <p className="text-xs text-muted-foreground">{product.length}/500 characters</p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="audience">
                Target Audience <span className="text-destructive">*</span>
              </Label>
              <Input
                id="audience"
                value={audience}
                onChange={(e) => setAudience(e.target.value)}
                placeholder="e.g., Busy professionals aged 25-45 looking to get fit"
                maxLength={300}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="benefits">
                Key Benefits <span className="text-destructive">*</span>
              </Label>
              <textarea
                id="benefits"
                value={benefits}
                onChange={(e) => setBenefits(e.target.value)}
                placeholder="e.g., Lose weight, build muscle, expert coaches, flexible scheduling, money-back guarantee"
                className="w-full min-h-[60px] px-3 py-2 rounded-md border border-input bg-background text-sm"
                maxLength={500}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="url">
                Landing Page URL <span className="text-destructive">*</span>
              </Label>
              <Input
                id="url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://example.com/landing-page"
                type="url"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="context">Additional Context (Optional)</Label>
              <Input
                id="context"
                value={additionalContext}
                onChange={(e) => setAdditionalContext(e.target.value)}
                placeholder="e.g., Focus on urgency, use numbers, mention discount"
                maxLength={500}
              />
            </div>

            {error && (
              <div className="p-3 rounded-lg bg-destructive/10 text-destructive text-sm">
                {error}
              </div>
            )}
          </div>
        )}

        {/* Generated Variations */}
        {variations.length > 0 && (
          <div className="space-y-4 py-4">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium">Select a variation to apply:</p>
              <Button
                variant="outline"
                size="sm"
                onClick={handleGenerate}
                disabled={isLoading}
              >
                <RefreshCw className={cn('h-4 w-4 mr-2', isLoading && 'animate-spin')} />
                Regenerate
              </Button>
            </div>

            <div className="space-y-3">
              {variations.map((variation, index) => (
                <div
                  key={index}
                  onClick={() => setSelectedIndex(index)}
                  className={cn(
                    'p-4 rounded-lg border cursor-pointer transition-colors',
                    selectedIndex === index
                      ? 'border-primary bg-primary/5'
                      : 'border-border hover:border-primary/50'
                  )}
                >
                  <div className="flex items-start justify-between mb-2">
                    <span className="text-xs font-medium text-muted-foreground px-2 py-1 rounded bg-muted">
                      {variation.variation_name}
                    </span>
                    {selectedIndex === index && (
                      <Check className="h-5 w-5 text-primary" />
                    )}
                  </div>

                  {/* Ad Preview */}
                  <div className="space-y-1">
                    <p className="text-primary font-medium">
                      {variation.headline_1}
                      {variation.headline_2 && ` | ${variation.headline_2}`}
                      {variation.headline_3 && ` | ${variation.headline_3}`}
                    </p>
                    <p className="text-sm text-muted-foreground">
                      {variation.description_1}
                      {variation.description_2 && ` ${variation.description_2}`}
                    </p>
                    <p className="text-xs text-primary mt-2">
                      CTA: {variation.cta}
                    </p>
                  </div>
                </div>
              ))}
            </div>

            <p className="text-xs text-muted-foreground flex items-center gap-1">
              <Sparkles className="h-3 w-3" />
              AI-generated content. Review and edit before publishing.
            </p>
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={handleClose}>
            Cancel
          </Button>

          {variations.length === 0 ? (
            <Button
              onClick={handleGenerate}
              disabled={!isFormValid || isLoading || (usageLimits?.is_limit_reached ?? false)}
            >
              {isLoading ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Generating...
                </>
              ) : (
                <>
                  <Sparkles className="h-4 w-4 mr-2" />
                  Generate Variations
                </>
              )}
            </Button>
          ) : (
            <Button onClick={handleApply} disabled={selectedIndex === null}>
              <Check className="h-4 w-4 mr-2" />
              Apply Selected
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
