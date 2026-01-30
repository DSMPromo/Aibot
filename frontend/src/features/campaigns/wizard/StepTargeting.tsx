import { useState } from 'react'
import { X, Plus } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { cn } from '@/lib/utils'
import type { WizardFormData } from '../CampaignWizard'

const popularLocations = [
  { code: 'US', name: 'United States' },
  { code: 'CA', name: 'Canada' },
  { code: 'UK', name: 'United Kingdom' },
  { code: 'AU', name: 'Australia' },
  { code: 'DE', name: 'Germany' },
  { code: 'FR', name: 'France' },
]

const genderOptions = [
  { id: 'all', label: 'All Genders' },
  { id: 'male', label: 'Male' },
  { id: 'female', label: 'Female' },
]

interface StepTargetingProps {
  formData: WizardFormData
  errors: Record<string, string>
  updateFormData: (updates: Partial<WizardFormData>) => void
}

export function StepTargeting({
  formData,
  errors,
  updateFormData,
}: StepTargetingProps) {
  const [newKeyword, setNewKeyword] = useState('')
  const [newInterest, setNewInterest] = useState('')

  const updateTargeting = (updates: Partial<WizardFormData['targeting']>) => {
    updateFormData({
      targeting: { ...formData.targeting, ...updates },
    })
  }

  const toggleLocation = (code: string) => {
    const locations = formData.targeting.locations.includes(code)
      ? formData.targeting.locations.filter((l) => l !== code)
      : [...formData.targeting.locations, code]
    updateTargeting({ locations })
  }

  const addKeyword = () => {
    if (newKeyword.trim() && !formData.targeting.keywords.includes(newKeyword.trim())) {
      updateTargeting({ keywords: [...formData.targeting.keywords, newKeyword.trim()] })
      setNewKeyword('')
    }
  }

  const removeKeyword = (keyword: string) => {
    updateTargeting({ keywords: formData.targeting.keywords.filter((k) => k !== keyword) })
  }

  const addInterest = () => {
    if (newInterest.trim() && !formData.targeting.interests.includes(newInterest.trim())) {
      updateTargeting({ interests: [...formData.targeting.interests, newInterest.trim()] })
      setNewInterest('')
    }
  }

  const removeInterest = (interest: string) => {
    updateTargeting({ interests: formData.targeting.interests.filter((i) => i !== interest) })
  }

  return (
    <div className="space-y-6">
      {/* Locations */}
      <div className="space-y-3">
        <Label>
          Locations <span className="text-destructive">*</span>
        </Label>
        <div className="flex flex-wrap gap-2">
          {popularLocations.map((location) => (
            <button
              key={location.code}
              type="button"
              onClick={() => toggleLocation(location.code)}
              className={cn(
                'px-3 py-1.5 rounded-full text-sm font-medium transition-colors',
                formData.targeting.locations.includes(location.code)
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-muted hover:bg-muted/80'
              )}
            >
              {location.name}
            </button>
          ))}
        </div>
        {errors.locations && (
          <p className="text-sm text-destructive">{errors.locations}</p>
        )}
        <p className="text-xs text-muted-foreground">
          Select one or more target locations
        </p>
      </div>

      {/* Age Range */}
      <div className="space-y-3">
        <Label>Age Range</Label>
        <div className="flex items-center gap-4">
          <div className="flex-1">
            <Label htmlFor="age_min" className="text-xs text-muted-foreground">
              Minimum Age
            </Label>
            <Input
              id="age_min"
              type="number"
              min="13"
              max={formData.targeting.age_max}
              value={formData.targeting.age_min}
              onChange={(e) => updateTargeting({ age_min: parseInt(e.target.value) || 18 })}
            />
          </div>
          <span className="mt-5">to</span>
          <div className="flex-1">
            <Label htmlFor="age_max" className="text-xs text-muted-foreground">
              Maximum Age
            </Label>
            <Input
              id="age_max"
              type="number"
              min={formData.targeting.age_min}
              max="65"
              value={formData.targeting.age_max}
              onChange={(e) => updateTargeting({ age_max: parseInt(e.target.value) || 65 })}
            />
          </div>
        </div>
      </div>

      {/* Gender */}
      <div className="space-y-3">
        <Label>Gender</Label>
        <div className="flex gap-4">
          {genderOptions.map((option) => (
            <label
              key={option.id}
              className={cn(
                'flex items-center gap-2 px-4 py-2 rounded-lg border cursor-pointer transition-colors',
                formData.targeting.genders.includes(option.id)
                  ? 'border-primary bg-primary/5'
                  : 'hover:bg-muted'
              )}
            >
              <input
                type="checkbox"
                checked={formData.targeting.genders.includes(option.id)}
                onChange={(e) => {
                  if (option.id === 'all') {
                    updateTargeting({ genders: e.target.checked ? ['all'] : [] })
                  } else {
                    const newGenders = e.target.checked
                      ? [...formData.targeting.genders.filter((g) => g !== 'all'), option.id]
                      : formData.targeting.genders.filter((g) => g !== option.id)
                    updateTargeting({ genders: newGenders.length ? newGenders : ['all'] })
                  }
                }}
                className="sr-only"
              />
              <span className="text-sm font-medium">{option.label}</span>
            </label>
          ))}
        </div>
      </div>

      {/* Keywords */}
      <div className="space-y-3">
        <Label>Keywords (optional)</Label>
        <div className="flex gap-2">
          <Input
            value={newKeyword}
            onChange={(e) => setNewKeyword(e.target.value)}
            placeholder="Add a keyword"
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault()
                addKeyword()
              }
            }}
          />
          <Button type="button" onClick={addKeyword} variant="outline">
            <Plus className="h-4 w-4" />
          </Button>
        </div>
        {formData.targeting.keywords.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {formData.targeting.keywords.map((keyword) => (
              <span
                key={keyword}
                className="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-muted text-sm"
              >
                {keyword}
                <button
                  type="button"
                  onClick={() => removeKeyword(keyword)}
                  className="hover:text-destructive"
                >
                  <X className="h-3 w-3" />
                </button>
              </span>
            ))}
          </div>
        )}
        <p className="text-xs text-muted-foreground">
          Keywords help target users searching for specific terms
        </p>
      </div>

      {/* Interests */}
      <div className="space-y-3">
        <Label>Interests (optional)</Label>
        <div className="flex gap-2">
          <Input
            value={newInterest}
            onChange={(e) => setNewInterest(e.target.value)}
            placeholder="Add an interest"
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault()
                addInterest()
              }
            }}
          />
          <Button type="button" onClick={addInterest} variant="outline">
            <Plus className="h-4 w-4" />
          </Button>
        </div>
        {formData.targeting.interests.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {formData.targeting.interests.map((interest) => (
              <span
                key={interest}
                className="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-muted text-sm"
              >
                {interest}
                <button
                  type="button"
                  onClick={() => removeInterest(interest)}
                  className="hover:text-destructive"
                >
                  <X className="h-3 w-3" />
                </button>
              </span>
            ))}
          </div>
        )}
        <p className="text-xs text-muted-foreground">
          Target users based on their interests and behaviors
        </p>
      </div>

      {/* Targeting Summary */}
      <div className="p-4 rounded-lg bg-muted">
        <h4 className="font-medium mb-2">Targeting Summary</h4>
        <div className="space-y-1 text-sm">
          <div className="flex justify-between">
            <span className="text-muted-foreground">Locations</span>
            <span>{formData.targeting.locations.join(', ') || 'None selected'}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Age</span>
            <span>{formData.targeting.age_min} - {formData.targeting.age_max}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Gender</span>
            <span className="capitalize">{formData.targeting.genders.join(', ')}</span>
          </div>
        </div>
      </div>
    </div>
  )
}
