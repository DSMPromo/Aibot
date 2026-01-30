import { useState, useEffect } from 'react'
import {
  Zap,
  Plus,
  Trash2,
  Play,
  Pause,
  Check,
  X,
  Clock,
  AlertTriangle,
  Loader2,
  ToggleLeft,
  ToggleRight,
  ChevronRight,
  Settings,
  History,
  FileText,
  RefreshCw,
} from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
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
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '@/components/ui/tabs'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import {
  automationApi,
  type AutomationRule,
  type PendingAction,
  type RuleTemplate,
  type ConditionType,
  type ActionType,
  type AutomationCondition,
  type AutomationAction,
} from '@/lib/api'

const operatorLabels: Record<string, string> = {
  gt: 'Greater than',
  lt: 'Less than',
  gte: 'Greater or equal',
  lte: 'Less or equal',
  eq: 'Equal to',
  change_gt: 'Increased by more than',
  change_lt: 'Decreased by more than',
}

const statusColors: Record<string, string> = {
  active: 'bg-green-100 text-green-700',
  paused: 'bg-yellow-100 text-yellow-700',
  draft: 'bg-gray-100 text-gray-700',
}

const actionStatusColors: Record<string, string> = {
  pending: 'bg-yellow-100 text-yellow-700',
  approved: 'bg-green-100 text-green-700',
  rejected: 'bg-red-100 text-red-700',
  expired: 'bg-gray-100 text-gray-700',
}

export default function AutomationPage() {
  const [activeTab, setActiveTab] = useState('rules')
  const [rules, setRules] = useState<AutomationRule[]>([])
  const [pendingActions, setPendingActions] = useState<PendingAction[]>([])
  const [templates, setTemplates] = useState<RuleTemplate[]>([])
  const [conditionTypes, setConditionTypes] = useState<Record<string, ConditionType>>({})
  const [actionTypes, setActionTypes] = useState<Record<string, ActionType>>({})
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Dialog states
  const [isCreateOpen, setIsCreateOpen] = useState(false)
  const [isTemplateOpen, setIsTemplateOpen] = useState(false)
  const [selectedTemplate, setSelectedTemplate] = useState<RuleTemplate | null>(null)
  const [isCreating, setIsCreating] = useState(false)

  // Form state for new rule
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    scope_type: 'org' as 'org' | 'campaign',
    conditions_operator: 'and' as 'and' | 'or',
    conditions: [{ metric: 'cpa', operator: 'gt', threshold: 50, lookback_days: 7 }] as AutomationCondition[],
    actions: [{ type: 'notify', params: { message: 'Rule triggered' } }] as AutomationAction[],
    requires_approval: true,
    cooldown_minutes: 60,
  })

  // Template form state
  const [templateFormData, setTemplateFormData] = useState<{
    name: string
    parameter_values: Record<string, unknown>
  }>({
    name: '',
    parameter_values: {},
  })

  const loadData = async () => {
    setIsLoading(true)
    setError(null)
    try {
      const [rulesRes, pendingRes, templatesRes, conditionsRes, actionsRes] = await Promise.all([
        automationApi.listRules(),
        automationApi.getPendingActions({ status: 'pending' }),
        automationApi.getTemplates(),
        automationApi.getConditionTypes(),
        automationApi.getActionTypes(),
      ])
      setRules(rulesRes.rules)
      setPendingActions(pendingRes.pending_actions)
      setTemplates(templatesRes.templates)
      setConditionTypes(conditionsRes.condition_types)
      setActionTypes(actionsRes.action_types)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load automation data')
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  const handleToggleRule = async (rule: AutomationRule) => {
    try {
      if (rule.status === 'active') {
        const updated = await automationApi.pauseRule(rule.id)
        setRules((prev) => prev.map((r) => (r.id === rule.id ? updated : r)))
      } else {
        const updated = await automationApi.activateRule(rule.id)
        setRules((prev) => prev.map((r) => (r.id === rule.id ? updated : r)))
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update rule')
    }
  }

  const handleDeleteRule = async (ruleId: string) => {
    if (!confirm('Are you sure you want to delete this rule?')) return

    try {
      await automationApi.deleteRule(ruleId)
      setRules((prev) => prev.filter((r) => r.id !== ruleId))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete rule')
    }
  }

  const handleRunRule = async (ruleId: string) => {
    try {
      await automationApi.runRule(ruleId)
      await loadData()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to run rule')
    }
  }

  const handleApprovePendingAction = async (actionId: string) => {
    try {
      await automationApi.approvePendingAction(actionId)
      setPendingActions((prev) => prev.filter((a) => a.id !== actionId))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to approve action')
    }
  }

  const handleRejectPendingAction = async (actionId: string) => {
    try {
      await automationApi.rejectPendingAction(actionId)
      setPendingActions((prev) => prev.filter((a) => a.id !== actionId))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to reject action')
    }
  }

  const handleCreateRule = async () => {
    setIsCreating(true)
    try {
      const newRule = await automationApi.createRule({
        name: formData.name,
        description: formData.description || undefined,
        scope_type: formData.scope_type,
        conditions: {
          operator: formData.conditions_operator,
          conditions: formData.conditions,
        },
        actions: formData.actions,
        requires_approval: formData.requires_approval,
        cooldown_minutes: formData.cooldown_minutes,
      })
      setRules((prev) => [newRule, ...prev])
      setIsCreateOpen(false)
      resetForm()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create rule')
    } finally {
      setIsCreating(false)
    }
  }

  const handleCreateFromTemplate = async () => {
    if (!selectedTemplate) return
    setIsCreating(true)
    try {
      const newRule = await automationApi.createRuleFromTemplate(selectedTemplate.id, {
        name: templateFormData.name,
        parameter_values: templateFormData.parameter_values,
      })
      setRules((prev) => [newRule, ...prev])
      setIsTemplateOpen(false)
      setSelectedTemplate(null)
      setTemplateFormData({ name: '', parameter_values: {} })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create rule from template')
    } finally {
      setIsCreating(false)
    }
  }

  const resetForm = () => {
    setFormData({
      name: '',
      description: '',
      scope_type: 'org',
      conditions_operator: 'and',
      conditions: [{ metric: 'cpa', operator: 'gt', threshold: 50, lookback_days: 7 }],
      actions: [{ type: 'notify', params: { message: 'Rule triggered' } }],
      requires_approval: true,
      cooldown_minutes: 60,
    })
  }

  const addCondition = () => {
    setFormData((prev) => ({
      ...prev,
      conditions: [
        ...prev.conditions,
        { metric: 'cpa', operator: 'gt', threshold: 50, lookback_days: 7 },
      ],
    }))
  }

  const removeCondition = (index: number) => {
    setFormData((prev) => ({
      ...prev,
      conditions: prev.conditions.filter((_, i) => i !== index),
    }))
  }

  const updateCondition = (index: number, field: string, value: unknown) => {
    setFormData((prev) => ({
      ...prev,
      conditions: prev.conditions.map((c, i) =>
        i === index ? { ...c, [field]: value } : c
      ),
    }))
  }

  const addAction = () => {
    setFormData((prev) => ({
      ...prev,
      actions: [...prev.actions, { type: 'notify', params: { message: '' } }],
    }))
  }

  const removeAction = (index: number) => {
    setFormData((prev) => ({
      ...prev,
      actions: prev.actions.filter((_, i) => i !== index),
    }))
  }

  const updateAction = (index: number, field: string, value: unknown) => {
    setFormData((prev) => ({
      ...prev,
      actions: prev.actions.map((a, i) =>
        i === index ? { ...a, [field]: value } : a
      ),
    }))
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
          <h1 className="text-2xl font-bold">Automation Rules</h1>
          <p className="text-muted-foreground">
            Automate campaign actions based on performance metrics
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => setIsTemplateOpen(true)}>
            <FileText className="h-4 w-4 mr-2" />
            From Template
          </Button>
          <Button onClick={() => setIsCreateOpen(true)}>
            <Plus className="h-4 w-4 mr-2" />
            Create Rule
          </Button>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-destructive/10 border border-destructive rounded-lg text-destructive text-sm">
          {error}
        </div>
      )}

      {/* Pending Actions Alert */}
      {pendingActions.length > 0 && (
        <Card className="border-yellow-200 bg-yellow-50">
          <CardContent className="flex items-center justify-between p-4">
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 rounded-full bg-yellow-100 flex items-center justify-center">
                <Clock className="h-5 w-5 text-yellow-600" />
              </div>
              <div>
                <h3 className="font-medium text-yellow-800">
                  {pendingActions.length} Pending Action{pendingActions.length > 1 ? 's' : ''} Awaiting Approval
                </h3>
                <p className="text-sm text-yellow-600">
                  Review and approve automation actions before they execute
                </p>
              </div>
            </div>
            <Button
              variant="outline"
              className="border-yellow-300 text-yellow-700 hover:bg-yellow-100"
              onClick={() => setActiveTab('pending')}
            >
              Review Now
              <ChevronRight className="h-4 w-4 ml-2" />
            </Button>
          </CardContent>
        </Card>
      )}

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="rules" className="flex items-center gap-2">
            <Zap className="h-4 w-4" />
            Rules ({rules.length})
          </TabsTrigger>
          <TabsTrigger value="pending" className="flex items-center gap-2">
            <Clock className="h-4 w-4" />
            Pending Actions
            {pendingActions.length > 0 && (
              <Badge variant="secondary" className="ml-1">
                {pendingActions.length}
              </Badge>
            )}
          </TabsTrigger>
          <TabsTrigger value="templates" className="flex items-center gap-2">
            <FileText className="h-4 w-4" />
            Templates
          </TabsTrigger>
        </TabsList>

        {/* Rules Tab */}
        <TabsContent value="rules" className="space-y-4">
          {rules.length === 0 ? (
            <Card>
              <CardContent className="flex flex-col items-center justify-center py-12">
                <Zap className="h-12 w-12 text-muted-foreground mb-4" />
                <h3 className="text-lg font-semibold mb-2">No automation rules</h3>
                <p className="text-muted-foreground text-center mb-4">
                  Create rules to automatically manage your campaigns based on performance
                </p>
                <div className="flex gap-2">
                  <Button variant="outline" onClick={() => setIsTemplateOpen(true)}>
                    <FileText className="h-4 w-4 mr-2" />
                    Start from Template
                  </Button>
                  <Button onClick={() => setIsCreateOpen(true)}>
                    <Plus className="h-4 w-4 mr-2" />
                    Create Custom Rule
                  </Button>
                </div>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-4">
              {rules.map((rule) => (
                <Card key={rule.id} className={cn(rule.status === 'paused' && 'opacity-60')}>
                  <CardContent className="p-4">
                    <div className="flex items-start justify-between">
                      <div className="flex items-start gap-4">
                        <div
                          className={cn(
                            'h-10 w-10 rounded-lg flex items-center justify-center',
                            rule.status === 'active'
                              ? 'bg-green-100 text-green-600'
                              : 'bg-gray-100 text-gray-600'
                          )}
                        >
                          <Zap className="h-5 w-5" />
                        </div>
                        <div className="space-y-1">
                          <div className="flex items-center gap-2">
                            <h3 className="font-medium">{rule.name}</h3>
                            <Badge className={statusColors[rule.status]}>{rule.status}</Badge>
                            {rule.requires_approval && (
                              <Badge variant="outline" className="text-xs">
                                Requires Approval
                              </Badge>
                            )}
                          </div>
                          {rule.description && (
                            <p className="text-sm text-muted-foreground">{rule.description}</p>
                          )}
                          <div className="flex items-center gap-4 text-xs text-muted-foreground">
                            <span>
                              Scope: {rule.scope_type === 'org' ? 'All Campaigns' : 'Specific Campaign'}
                            </span>
                            {rule.platform && <span>Platform: {rule.platform}</span>}
                            <span>Cooldown: {rule.cooldown_minutes} min</span>
                            {rule.execution_count > 0 && (
                              <span>Executions: {rule.execution_count}</span>
                            )}
                          </div>
                          {/* Conditions summary */}
                          <div className="flex flex-wrap gap-2 mt-2">
                            {rule.conditions.conditions.map((cond, idx) => (
                              <Badge key={idx} variant="secondary" className="text-xs">
                                {conditionTypes[cond.metric]?.label || cond.metric}{' '}
                                {operatorLabels[cond.operator] || cond.operator} {cond.threshold}
                                {conditionTypes[cond.metric]?.unit}
                              </Badge>
                            ))}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleRunRule(rule.id)}
                          title="Run now"
                        >
                          <Play className="h-4 w-4" />
                        </Button>
                        <button
                          onClick={() => handleToggleRule(rule)}
                          className="p-2 hover:bg-muted rounded-lg transition-colors"
                          title={rule.status === 'active' ? 'Pause' : 'Activate'}
                        >
                          {rule.status === 'active' ? (
                            <ToggleRight className="h-6 w-6 text-primary" />
                          ) : (
                            <ToggleLeft className="h-6 w-6 text-muted-foreground" />
                          )}
                        </button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleDeleteRule(rule.id)}
                        >
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>

        {/* Pending Actions Tab */}
        <TabsContent value="pending" className="space-y-4">
          {pendingActions.length === 0 ? (
            <Card>
              <CardContent className="flex flex-col items-center justify-center py-12">
                <Check className="h-12 w-12 text-muted-foreground mb-4" />
                <h3 className="text-lg font-semibold mb-2">No pending actions</h3>
                <p className="text-muted-foreground text-center">
                  All automation actions have been reviewed
                </p>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-4">
              {pendingActions.map((action) => (
                <Card key={action.id} className="border-yellow-200">
                  <CardContent className="p-4">
                    <div className="flex items-start justify-between">
                      <div className="space-y-2">
                        <div className="flex items-center gap-2">
                          <AlertTriangle className="h-5 w-5 text-yellow-500" />
                          <h3 className="font-medium">
                            {actionTypes[action.action_type]?.label || action.action_type}
                          </h3>
                          <Badge className={actionStatusColors[action.status]}>
                            {action.status}
                          </Badge>
                        </div>
                        <p className="text-sm text-muted-foreground">
                          Rule: <span className="font-medium">{action.rule_name}</span> |
                          Campaign: <span className="font-medium">{action.campaign_name}</span>
                        </p>
                        <p className="text-sm">{action.trigger_reason}</p>
                        <div className="flex items-center gap-4 text-xs text-muted-foreground">
                          <span>
                            Created: {new Date(action.created_at).toLocaleString()}
                          </span>
                          <span>
                            Expires: {new Date(action.expires_at).toLocaleString()}
                          </span>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          className="text-red-600 border-red-200 hover:bg-red-50"
                          onClick={() => handleRejectPendingAction(action.id)}
                        >
                          <X className="h-4 w-4 mr-1" />
                          Reject
                        </Button>
                        <Button
                          size="sm"
                          className="bg-green-600 hover:bg-green-700"
                          onClick={() => handleApprovePendingAction(action.id)}
                        >
                          <Check className="h-4 w-4 mr-1" />
                          Approve
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>

        {/* Templates Tab */}
        <TabsContent value="templates" className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {templates.map((template) => (
              <Card
                key={template.id}
                className="cursor-pointer hover:border-primary transition-colors"
                onClick={() => {
                  setSelectedTemplate(template)
                  setTemplateFormData({
                    name: template.name,
                    parameter_values: template.parameters.reduce(
                      (acc, p) => ({ ...acc, [p.name]: p.default_value }),
                      {}
                    ),
                  })
                  setIsTemplateOpen(true)
                }}
              >
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <Badge variant="outline">{template.category}</Badge>
                    {template.applicable_platforms.length > 0 && (
                      <div className="flex gap-1">
                        {template.applicable_platforms.map((p) => (
                          <Badge key={p} variant="secondary" className="text-xs">
                            {p}
                          </Badge>
                        ))}
                      </div>
                    )}
                  </div>
                  <CardTitle className="text-lg">{template.name}</CardTitle>
                  <CardDescription>{template.description}</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center justify-between text-sm text-muted-foreground">
                    <span>{template.parameters.length} configurable parameters</span>
                    <ChevronRight className="h-4 w-4" />
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>
      </Tabs>

      {/* Create Rule Dialog */}
      <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Create Automation Rule</DialogTitle>
            <DialogDescription>
              Configure conditions and actions for your automation rule
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-6 py-4">
            {/* Basic Info */}
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="name">Rule Name</Label>
                <Input
                  id="name"
                  placeholder="e.g., Pause High CPA Campaigns"
                  value={formData.name}
                  onChange={(e) => setFormData((prev) => ({ ...prev, name: e.target.value }))}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="description">Description (optional)</Label>
                <Textarea
                  id="description"
                  placeholder="Describe what this rule does..."
                  value={formData.description}
                  onChange={(e) => setFormData((prev) => ({ ...prev, description: e.target.value }))}
                />
              </div>
            </div>

            {/* Conditions */}
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <Label>Conditions</Label>
                <Select
                  value={formData.conditions_operator}
                  onValueChange={(value: 'and' | 'or') =>
                    setFormData((prev) => ({ ...prev, conditions_operator: value }))
                  }
                >
                  <SelectTrigger className="w-32">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="and">Match ALL</SelectItem>
                    <SelectItem value="or">Match ANY</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {formData.conditions.map((condition, index) => (
                <div key={index} className="flex items-end gap-2 p-3 bg-muted rounded-lg">
                  <div className="flex-1 space-y-2">
                    <Label className="text-xs">Metric</Label>
                    <Select
                      value={condition.metric}
                      onValueChange={(value) => updateCondition(index, 'metric', value)}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {Object.entries(conditionTypes).map(([key, ct]) => (
                          <SelectItem key={key} value={key}>
                            {ct.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="flex-1 space-y-2">
                    <Label className="text-xs">Operator</Label>
                    <Select
                      value={condition.operator}
                      onValueChange={(value) => updateCondition(index, 'operator', value)}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {(conditionTypes[condition.metric]?.operators || ['gt', 'lt', 'gte', 'lte']).map(
                          (op) => (
                            <SelectItem key={op} value={op}>
                              {operatorLabels[op] || op}
                            </SelectItem>
                          )
                        )}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="w-24 space-y-2">
                    <Label className="text-xs">Threshold</Label>
                    <Input
                      type="number"
                      step="0.01"
                      value={condition.threshold}
                      onChange={(e) =>
                        updateCondition(index, 'threshold', parseFloat(e.target.value))
                      }
                    />
                  </div>
                  <div className="w-20 space-y-2">
                    <Label className="text-xs">Days</Label>
                    <Input
                      type="number"
                      min="1"
                      max="90"
                      value={condition.lookback_days || 7}
                      onChange={(e) =>
                        updateCondition(index, 'lookback_days', parseInt(e.target.value))
                      }
                    />
                  </div>
                  {formData.conditions.length > 1 && (
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => removeCondition(index)}
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  )}
                </div>
              ))}

              <Button variant="outline" size="sm" onClick={addCondition}>
                <Plus className="h-4 w-4 mr-2" />
                Add Condition
              </Button>
            </div>

            {/* Actions */}
            <div className="space-y-4">
              <Label>Actions</Label>

              {formData.actions.map((action, index) => (
                <div key={index} className="flex items-end gap-2 p-3 bg-muted rounded-lg">
                  <div className="flex-1 space-y-2">
                    <Label className="text-xs">Action Type</Label>
                    <Select
                      value={action.type}
                      onValueChange={(value) => updateAction(index, 'type', value)}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {Object.entries(actionTypes).map(([key, at]) => (
                          <SelectItem key={key} value={key}>
                            {at.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  {action.type === 'notify' && (
                    <div className="flex-1 space-y-2">
                      <Label className="text-xs">Message</Label>
                      <Input
                        placeholder="Notification message..."
                        value={(action.params as { message?: string })?.message || ''}
                        onChange={(e) =>
                          updateAction(index, 'params', { ...action.params, message: e.target.value })
                        }
                      />
                    </div>
                  )}
                  {action.type === 'adjust_budget' && (
                    <div className="flex-1 space-y-2">
                      <Label className="text-xs">Adjustment %</Label>
                      <Input
                        type="number"
                        step="1"
                        placeholder="-10"
                        value={(action.params as { adjustment_percent?: number })?.adjustment_percent || ''}
                        onChange={(e) =>
                          updateAction(index, 'params', {
                            ...action.params,
                            adjustment_percent: parseInt(e.target.value),
                          })
                        }
                      />
                    </div>
                  )}
                  {formData.actions.length > 1 && (
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => removeAction(index)}
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  )}
                </div>
              ))}

              <Button variant="outline" size="sm" onClick={addAction}>
                <Plus className="h-4 w-4 mr-2" />
                Add Action
              </Button>
            </div>

            {/* Settings */}
            <div className="space-y-4">
              <Label>Settings</Label>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="cooldown" className="text-sm">Cooldown (minutes)</Label>
                  <Input
                    id="cooldown"
                    type="number"
                    min="5"
                    value={formData.cooldown_minutes}
                    onChange={(e) =>
                      setFormData((prev) => ({
                        ...prev,
                        cooldown_minutes: parseInt(e.target.value),
                      }))
                    }
                  />
                </div>
                <div className="flex items-center space-x-2 pt-6">
                  <input
                    type="checkbox"
                    id="requires_approval"
                    checked={formData.requires_approval}
                    onChange={(e) =>
                      setFormData((prev) => ({
                        ...prev,
                        requires_approval: e.target.checked,
                      }))
                    }
                    className="h-4 w-4 rounded border-gray-300"
                  />
                  <Label htmlFor="requires_approval" className="text-sm">
                    Require approval before execution
                  </Label>
                </div>
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setIsCreateOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleCreateRule} disabled={!formData.name || isCreating}>
              {isCreating && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              Create Rule
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Create from Template Dialog */}
      <Dialog open={isTemplateOpen} onOpenChange={setIsTemplateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {selectedTemplate ? `Create from: ${selectedTemplate.name}` : 'Select Template'}
            </DialogTitle>
            <DialogDescription>
              {selectedTemplate?.description || 'Choose a template to get started quickly'}
            </DialogDescription>
          </DialogHeader>

          {selectedTemplate && (
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="template-name">Rule Name</Label>
                <Input
                  id="template-name"
                  value={templateFormData.name}
                  onChange={(e) =>
                    setTemplateFormData((prev) => ({ ...prev, name: e.target.value }))
                  }
                />
              </div>

              {selectedTemplate.parameters.map((param) => (
                <div key={param.name} className="space-y-2">
                  <Label htmlFor={param.name}>
                    {param.label}
                    {param.required && <span className="text-destructive ml-1">*</span>}
                  </Label>
                  {param.description && (
                    <p className="text-xs text-muted-foreground">{param.description}</p>
                  )}
                  <Input
                    id={param.name}
                    type={param.type === 'number' ? 'number' : 'text'}
                    value={String(templateFormData.parameter_values[param.name] ?? '')}
                    onChange={(e) =>
                      setTemplateFormData((prev) => ({
                        ...prev,
                        parameter_values: {
                          ...prev.parameter_values,
                          [param.name]:
                            param.type === 'number'
                              ? parseFloat(e.target.value)
                              : e.target.value,
                        },
                      }))
                    }
                  />
                </div>
              ))}
            </div>
          )}

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setIsTemplateOpen(false)
                setSelectedTemplate(null)
              }}
            >
              Cancel
            </Button>
            <Button
              onClick={handleCreateFromTemplate}
              disabled={!templateFormData.name || isCreating}
            >
              {isCreating && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              Create Rule
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
