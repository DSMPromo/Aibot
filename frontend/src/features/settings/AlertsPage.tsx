import { useState, useEffect } from 'react'
import {
  Bell,
  Plus,
  Trash2,
  AlertTriangle,
  DollarSign,
  TrendingUp,
  Target,
  Loader2,
  ToggleLeft,
  ToggleRight,
} from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { cn } from '@/lib/utils'
import { alertsApi, type Alert, type AlertCreate } from '@/lib/api'

const alertTypeLabels: Record<string, { label: string; icon: typeof DollarSign }> = {
  budget_threshold: { label: 'Budget Threshold', icon: DollarSign },
  cpa_threshold: { label: 'CPA Threshold', icon: Target },
  roas_threshold: { label: 'ROAS Threshold', icon: TrendingUp },
  ctr_threshold: { label: 'CTR Threshold', icon: TrendingUp },
}

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isCreateOpen, setIsCreateOpen] = useState(false)
  const [isCreating, setIsCreating] = useState(false)

  // Form state
  const [formData, setFormData] = useState<{
    name: string
    alert_type: AlertCreate['alert_type']
    threshold_percent?: number
    budget_type?: string
    budget_amount?: number
    metric?: string
    operator?: string
    threshold?: number
    lookback_days?: number
  }>({
    name: '',
    alert_type: 'budget_threshold',
    threshold_percent: 80,
    budget_type: 'daily',
    budget_amount: 1000,
    metric: 'cpa',
    operator: 'gt',
    threshold: 50,
    lookback_days: 7,
  })

  const loadAlerts = async () => {
    setIsLoading(true)
    setError(null)
    try {
      const response = await alertsApi.listAlerts()
      setAlerts(response.alerts)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load alerts')
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    loadAlerts()
  }, [])

  const handleToggleAlert = async (alert: Alert) => {
    try {
      await alertsApi.updateAlert(alert.id, { is_enabled: !alert.is_enabled })
      setAlerts((prev) =>
        prev.map((a) =>
          a.id === alert.id ? { ...a, is_enabled: !a.is_enabled } : a
        )
      )
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update alert')
    }
  }

  const handleDeleteAlert = async (alertId: string) => {
    if (!confirm('Are you sure you want to delete this alert?')) return

    try {
      await alertsApi.deleteAlert(alertId)
      setAlerts((prev) => prev.filter((a) => a.id !== alertId))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete alert')
    }
  }

  const handleCreateAlert = async () => {
    setIsCreating(true)
    try {
      const config =
        formData.alert_type === 'budget_threshold'
          ? {
              threshold_percent: formData.threshold_percent,
              budget_type: formData.budget_type,
              budget_amount: formData.budget_amount,
            }
          : {
              metric: formData.alert_type.replace('_threshold', ''),
              operator: formData.operator,
              threshold: formData.threshold,
              lookback_days: formData.lookback_days,
            }

      const newAlert = await alertsApi.createAlert({
        name: formData.name,
        alert_type: formData.alert_type,
        config,
      })

      setAlerts((prev) => [newAlert, ...prev])
      setIsCreateOpen(false)
      setFormData({
        name: '',
        alert_type: 'budget_threshold',
        threshold_percent: 80,
        budget_type: 'daily',
        budget_amount: 1000,
        metric: 'cpa',
        operator: 'gt',
        threshold: 50,
        lookback_days: 7,
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create alert')
    } finally {
      setIsCreating(false)
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">Budget & Performance Alerts</h2>
          <p className="text-sm text-muted-foreground">
            Get notified when your campaigns exceed thresholds
          </p>
        </div>
        <Button onClick={() => setIsCreateOpen(true)}>
          <Plus className="h-4 w-4 mr-2" />
          Create Alert
        </Button>
      </div>

      {error && (
        <div className="p-4 bg-destructive/10 border border-destructive rounded-lg text-destructive text-sm">
          {error}
        </div>
      )}

      {alerts.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <Bell className="h-12 w-12 text-muted-foreground mb-4" />
            <h3 className="text-lg font-semibold mb-2">No alerts configured</h3>
            <p className="text-muted-foreground text-center mb-4">
              Create an alert to get notified about budget usage or performance
              changes
            </p>
            <Button onClick={() => setIsCreateOpen(true)}>
              <Plus className="h-4 w-4 mr-2" />
              Create Your First Alert
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {alerts.map((alert) => {
            const typeInfo = alertTypeLabels[alert.alert_type] || {
              label: alert.alert_type,
              icon: AlertTriangle,
            }
            const TypeIcon = typeInfo.icon

            return (
              <Card
                key={alert.id}
                className={cn(!alert.is_enabled && 'opacity-60')}
              >
                <CardContent className="flex items-center justify-between p-4">
                  <div className="flex items-center gap-4">
                    <div
                      className={cn(
                        'h-10 w-10 rounded-lg flex items-center justify-center',
                        alert.is_triggered
                          ? 'bg-red-100 text-red-600'
                          : 'bg-primary/10 text-primary'
                      )}
                    >
                      <TypeIcon className="h-5 w-5" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="font-medium">{alert.name}</h3>
                        {alert.is_triggered && (
                          <span className="text-xs bg-red-100 text-red-600 px-2 py-0.5 rounded-full">
                            Triggered
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-muted-foreground">
                        {typeInfo.label} |{' '}
                        {alert.scope_type === 'org'
                          ? 'All Campaigns'
                          : 'Specific Campaign'}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => handleToggleAlert(alert)}
                      className="p-2 hover:bg-muted rounded-lg transition-colors"
                      title={alert.is_enabled ? 'Disable' : 'Enable'}
                    >
                      {alert.is_enabled ? (
                        <ToggleRight className="h-6 w-6 text-primary" />
                      ) : (
                        <ToggleLeft className="h-6 w-6 text-muted-foreground" />
                      )}
                    </button>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => handleDeleteAlert(alert.id)}
                    >
                      <Trash2 className="h-4 w-4 text-destructive" />
                    </Button>
                  </div>
                </CardContent>
              </Card>
            )
          })}
        </div>
      )}

      {/* Create Alert Dialog */}
      <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create Alert</DialogTitle>
            <DialogDescription>
              Configure a new alert to monitor your campaigns
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="name">Alert Name</Label>
              <Input
                id="name"
                placeholder="e.g., Daily Budget Warning"
                value={formData.name}
                onChange={(e) =>
                  setFormData((prev) => ({ ...prev, name: e.target.value }))
                }
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="type">Alert Type</Label>
              <Select
                value={formData.alert_type}
                onValueChange={(value: AlertCreate['alert_type']) =>
                  setFormData((prev) => ({ ...prev, alert_type: value }))
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="budget_threshold">
                    Budget Threshold
                  </SelectItem>
                  <SelectItem value="cpa_threshold">CPA Threshold</SelectItem>
                  <SelectItem value="roas_threshold">ROAS Threshold</SelectItem>
                  <SelectItem value="ctr_threshold">CTR Threshold</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {formData.alert_type === 'budget_threshold' ? (
              <>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="budget_type">Budget Period</Label>
                    <Select
                      value={formData.budget_type}
                      onValueChange={(value) =>
                        setFormData((prev) => ({ ...prev, budget_type: value }))
                      }
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="daily">Daily</SelectItem>
                        <SelectItem value="weekly">Weekly</SelectItem>
                        <SelectItem value="monthly">Monthly</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="budget_amount">Budget Amount ($)</Label>
                    <Input
                      id="budget_amount"
                      type="number"
                      min="0"
                      value={formData.budget_amount}
                      onChange={(e) =>
                        setFormData((prev) => ({
                          ...prev,
                          budget_amount: parseFloat(e.target.value),
                        }))
                      }
                    />
                  </div>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="threshold_percent">
                    Alert at (% of budget)
                  </Label>
                  <Input
                    id="threshold_percent"
                    type="number"
                    min="1"
                    max="100"
                    value={formData.threshold_percent}
                    onChange={(e) =>
                      setFormData((prev) => ({
                        ...prev,
                        threshold_percent: parseFloat(e.target.value),
                      }))
                    }
                  />
                  <p className="text-xs text-muted-foreground">
                    You'll be notified when spend reaches {formData.threshold_percent}% of your budget
                  </p>
                </div>
              </>
            ) : (
              <>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="operator">Condition</Label>
                    <Select
                      value={formData.operator}
                      onValueChange={(value) =>
                        setFormData((prev) => ({ ...prev, operator: value }))
                      }
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="gt">Greater than</SelectItem>
                        <SelectItem value="lt">Less than</SelectItem>
                        <SelectItem value="gte">Greater or equal</SelectItem>
                        <SelectItem value="lte">Less or equal</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="threshold">Threshold</Label>
                    <Input
                      id="threshold"
                      type="number"
                      step="0.01"
                      value={formData.threshold}
                      onChange={(e) =>
                        setFormData((prev) => ({
                          ...prev,
                          threshold: parseFloat(e.target.value),
                        }))
                      }
                    />
                  </div>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="lookback_days">Lookback Period (days)</Label>
                  <Input
                    id="lookback_days"
                    type="number"
                    min="1"
                    max="90"
                    value={formData.lookback_days}
                    onChange={(e) =>
                      setFormData((prev) => ({
                        ...prev,
                        lookback_days: parseInt(e.target.value),
                      }))
                    }
                  />
                </div>
              </>
            )}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setIsCreateOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleCreateAlert}
              disabled={!formData.name || isCreating}
            >
              {isCreating && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              Create Alert
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
