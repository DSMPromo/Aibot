import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ArrowLeft,
  ArrowRight,
  Check,
  Loader2,
  Target,
  DollarSign,
  Users,
  FileText,
  CheckCircle,
} from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useToast } from '@/hooks/use-toast'
import { useCampaignsStore } from '@/stores/campaigns'
import { useConnectionsStore } from '@/stores/connections'
import { cn } from '@/lib/utils'
import type { CampaignCreateRequest } from '@/lib/api'

// Step components
import { StepBasicInfo } from './wizard/StepBasicInfo'
import { StepBudget } from './wizard/StepBudget'
import { StepTargeting } from './wizard/StepTargeting'
import { StepAdCopy } from './wizard/StepAdCopy'
import { StepReview } from './wizard/StepReview'

const steps = [
  { id: 'basic', title: 'Basic Info', icon: Target },
  { id: 'budget', title: 'Budget', icon: DollarSign },
  { id: 'targeting', title: 'Targeting', icon: Users },
  { id: 'ad-copy', title: 'Ad Copy', icon: FileText },
  { id: 'review', title: 'Review', icon: CheckCircle },
]

export interface WizardFormData {
  // Step 1: Basic Info
  name: string
  description: string
  ad_account_id: string
  objective: string

  // Step 2: Budget
  budget_type: 'daily' | 'lifetime'
  budget_amount: number
  budget_currency: string
  start_date: string
  end_date: string
  is_ongoing: boolean

  // Step 3: Targeting
  targeting: {
    locations: string[]
    age_min: number
    age_max: number
    genders: string[]
    interests: string[]
    keywords: string[]
  }

  // Step 4: Ad Copy
  ad_copies: Array<{
    headline_1: string
    headline_2: string
    headline_3: string
    description_1: string
    description_2: string
    path_1: string
    path_2: string
    final_url: string
    call_to_action: string
    is_primary: boolean
  }>
}

const initialFormData: WizardFormData = {
  name: '',
  description: '',
  ad_account_id: '',
  objective: 'traffic',
  budget_type: 'daily',
  budget_amount: 50,
  budget_currency: 'USD',
  start_date: '',
  end_date: '',
  is_ongoing: true,
  targeting: {
    locations: ['US'],
    age_min: 18,
    age_max: 65,
    genders: ['all'],
    interests: [],
    keywords: [],
  },
  ad_copies: [
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
      is_primary: true,
    },
  ],
}

export default function CampaignWizard() {
  const navigate = useNavigate()
  const { toast } = useToast()
  const { createCampaign, isLoading } = useCampaignsStore()
  const { accounts } = useConnectionsStore()

  const [currentStep, setCurrentStep] = useState(0)
  const [formData, setFormData] = useState<WizardFormData>(initialFormData)
  const [errors, setErrors] = useState<Record<string, string>>({})

  const updateFormData = (updates: Partial<WizardFormData>) => {
    setFormData((prev) => ({ ...prev, ...updates }))
    // Clear related errors
    const errorKeys = Object.keys(updates)
    setErrors((prev) => {
      const newErrors = { ...prev }
      errorKeys.forEach((key) => delete newErrors[key])
      return newErrors
    })
  }

  const validateStep = (step: number): boolean => {
    const newErrors: Record<string, string> = {}

    switch (step) {
      case 0: // Basic Info
        if (!formData.name.trim()) newErrors.name = 'Campaign name is required'
        if (!formData.ad_account_id) newErrors.ad_account_id = 'Please select an ad account'
        if (!formData.objective) newErrors.objective = 'Please select an objective'
        break

      case 1: // Budget
        if (formData.budget_amount <= 0) newErrors.budget_amount = 'Budget must be greater than 0'
        if (!formData.is_ongoing && formData.start_date && formData.end_date) {
          if (new Date(formData.end_date) < new Date(formData.start_date)) {
            newErrors.end_date = 'End date must be after start date'
          }
        }
        break

      case 2: // Targeting
        if (formData.targeting.locations.length === 0) {
          newErrors.locations = 'Please select at least one location'
        }
        break

      case 3: // Ad Copy
        const primaryCopy = formData.ad_copies[0]
        if (!primaryCopy.headline_1.trim()) newErrors.headline_1 = 'Headline 1 is required'
        if (!primaryCopy.description_1.trim()) newErrors.description_1 = 'Description 1 is required'
        if (!primaryCopy.final_url.trim()) {
          newErrors.final_url = 'Landing page URL is required'
        } else if (!isValidUrl(primaryCopy.final_url)) {
          newErrors.final_url = 'Please enter a valid URL'
        }
        break
    }

    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  const isValidUrl = (url: string): boolean => {
    try {
      new URL(url)
      return true
    } catch {
      return false
    }
  }

  const handleNext = () => {
    if (validateStep(currentStep)) {
      setCurrentStep((prev) => Math.min(prev + 1, steps.length - 1))
    }
  }

  const handleBack = () => {
    setCurrentStep((prev) => Math.max(prev - 1, 0))
  }

  const handleSubmit = async (asDraft: boolean = false) => {
    if (!asDraft && !validateStep(currentStep)) return

    try {
      const campaignData: CampaignCreateRequest = {
        name: formData.name,
        description: formData.description || undefined,
        ad_account_id: formData.ad_account_id,
        objective: formData.objective,
        budget_type: formData.budget_type,
        budget_amount: formData.budget_amount,
        budget_currency: formData.budget_currency,
        start_date: formData.start_date || undefined,
        end_date: formData.end_date || undefined,
        is_ongoing: formData.is_ongoing,
        targeting: formData.targeting,
        ad_copies: formData.ad_copies.filter((c) => c.headline_1 && c.description_1 && c.final_url),
      }

      const campaign = await createCampaign(campaignData)

      toast({
        title: 'Campaign created',
        description: asDraft
          ? 'Campaign saved as draft.'
          : 'Campaign created successfully.',
      })

      navigate(`/campaigns/${campaign.id}`)
    } catch {
      toast({
        title: 'Error',
        description: 'Failed to create campaign.',
        variant: 'destructive',
      })
    }
  }

  const renderStepContent = () => {
    switch (currentStep) {
      case 0:
        return (
          <StepBasicInfo
            formData={formData}
            errors={errors}
            accounts={accounts}
            updateFormData={updateFormData}
          />
        )
      case 1:
        return (
          <StepBudget
            formData={formData}
            errors={errors}
            updateFormData={updateFormData}
          />
        )
      case 2:
        return (
          <StepTargeting
            formData={formData}
            errors={errors}
            updateFormData={updateFormData}
          />
        )
      case 3:
        // Get platform from selected ad account
        const selectedAccount = accounts.find(a => a.id === formData.ad_account_id)
        return (
          <StepAdCopy
            formData={formData}
            errors={errors}
            updateFormData={updateFormData}
            platform={selectedAccount?.platform || 'google'}
          />
        )
      case 4:
        return <StepReview formData={formData} accounts={accounts} />
      default:
        return null
    }
  }

  return (
    <div className="max-w-4xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold">Create Campaign</h1>
        <p className="text-muted-foreground">
          Set up a new advertising campaign
        </p>
      </div>

      {/* Step indicator */}
      <div className="mb-8">
        <div className="flex items-center justify-between">
          {steps.map((step, index) => (
            <div key={step.id} className="flex items-center">
              <div
                className={cn(
                  'flex items-center justify-center w-10 h-10 rounded-full border-2 transition-colors',
                  index < currentStep
                    ? 'bg-primary border-primary text-primary-foreground'
                    : index === currentStep
                    ? 'border-primary text-primary'
                    : 'border-muted text-muted-foreground'
                )}
              >
                {index < currentStep ? (
                  <Check className="h-5 w-5" />
                ) : (
                  <step.icon className="h-5 w-5" />
                )}
              </div>
              {index < steps.length - 1 && (
                <div
                  className={cn(
                    'w-full h-1 mx-2 rounded',
                    index < currentStep ? 'bg-primary' : 'bg-muted'
                  )}
                  style={{ minWidth: '60px' }}
                />
              )}
            </div>
          ))}
        </div>
        <div className="flex justify-between mt-2">
          {steps.map((step, index) => (
            <span
              key={step.id}
              className={cn(
                'text-xs',
                index === currentStep ? 'text-primary font-medium' : 'text-muted-foreground'
              )}
            >
              {step.title}
            </span>
          ))}
        </div>
      </div>

      {/* Step content */}
      <Card>
        <CardHeader>
          <CardTitle>{steps[currentStep].title}</CardTitle>
        </CardHeader>
        <CardContent>{renderStepContent()}</CardContent>
      </Card>

      {/* Navigation buttons */}
      <div className="flex items-center justify-between mt-6">
        <div>
          {currentStep > 0 && (
            <Button variant="outline" onClick={handleBack}>
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back
            </Button>
          )}
        </div>

        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={() => handleSubmit(true)} disabled={isLoading}>
            Save as Draft
          </Button>

          {currentStep < steps.length - 1 ? (
            <Button onClick={handleNext}>
              Next
              <ArrowRight className="h-4 w-4 ml-2" />
            </Button>
          ) : (
            <Button onClick={() => handleSubmit(false)} disabled={isLoading}>
              {isLoading && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              Create Campaign
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}
