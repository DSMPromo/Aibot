import { useEffect, useState } from 'react'
import {
  AlertCircle,
  Check,
  CreditCard,
  Download,
  ExternalLink,
  Loader2,
  Package,
  Receipt,
  Settings,
  Trash2,
  Zap,
} from 'lucide-react'

import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { useToast } from '@/hooks/use-toast'
import {
  billingApi,
  type SubscriptionResponse,
  type PlanInfo,
  type InvoiceResponse,
  type PaymentMethodResponse,
  type UsageSummaryResponse,
} from '@/lib/api'
import { cn } from '@/lib/utils'

function formatCurrency(cents: number, currency: string = 'usd'): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: currency.toUpperCase(),
  }).format(cents / 100)
}

function formatDate(dateString: string | null): string {
  if (!dateString) return 'N/A'
  return new Date(dateString).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

function formatLimit(value: number): string {
  if (value === -1) return 'Unlimited'
  return value.toLocaleString()
}

function PlanCard({
  plan,
  currentPlan,
  billingCycle,
  onSelect,
  isLoading,
}: {
  plan: PlanInfo
  currentPlan: string
  billingCycle: 'monthly' | 'yearly'
  onSelect: (priceId: string) => void
  isLoading: boolean
}) {
  const isCurrent = plan.id === currentPlan
  const isEnterprise = plan.id === 'enterprise'
  const price = billingCycle === 'yearly' ? plan.price_yearly : plan.price_monthly
  const priceId = billingCycle === 'yearly' ? plan.price_id_yearly : plan.price_id_monthly
  const isPopular = plan.id === 'pro'

  return (
    <Card className={cn(isPopular && 'border-primary shadow-md', isCurrent && 'bg-muted/50')}>
      {isPopular && (
        <div className="bg-primary text-primary-foreground text-xs font-medium px-3 py-1 text-center">
          Most Popular
        </div>
      )}
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          {plan.name}
          {isCurrent && (
            <span className="text-xs bg-primary/10 text-primary px-2 py-0.5 rounded">
              Current
            </span>
          )}
        </CardTitle>
        <div className="text-3xl font-bold">
          {isEnterprise ? (
            'Custom'
          ) : price !== null ? (
            <>
              {formatCurrency(price)}
              <span className="text-sm font-normal text-muted-foreground">
                /{billingCycle === 'yearly' ? 'year' : 'month'}
              </span>
            </>
          ) : (
            'Free'
          )}
        </div>
        <CardDescription>{plan.description}</CardDescription>
      </CardHeader>
      <CardContent>
        <ul className="space-y-2 text-sm mb-4">
          <li className="flex items-center gap-2">
            <Check className="h-4 w-4 text-green-500" />
            {formatLimit(plan.limits.ad_accounts)} ad account{plan.limits.ad_accounts !== 1 && 's'}
          </li>
          <li className="flex items-center gap-2">
            <Check className="h-4 w-4 text-green-500" />
            {formatLimit(plan.limits.ai_generations)} AI generations/month
          </li>
          <li className="flex items-center gap-2">
            <Check className="h-4 w-4 text-green-500" />
            {formatLimit(plan.limits.campaigns)} campaigns
          </li>
          <li className="flex items-center gap-2">
            <Check className="h-4 w-4 text-green-500" />
            {formatLimit(plan.limits.team_members)} team member{plan.limits.team_members !== 1 && 's'}
          </li>
          <li className="flex items-center gap-2">
            <Check className="h-4 w-4 text-green-500" />
            {formatLimit(plan.limits.automation_rules)} automation rules
          </li>
        </ul>
        {isEnterprise ? (
          <Button variant="outline" className="w-full" asChild>
            <a href="mailto:sales@aimarketing.com">Contact Sales</a>
          </Button>
        ) : (
          <Button
            className="w-full"
            variant={isCurrent ? 'outline' : 'default'}
            disabled={isCurrent || isLoading || !priceId}
            onClick={() => priceId && onSelect(priceId)}
          >
            {isLoading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : isCurrent ? (
              'Current Plan'
            ) : (
              'Upgrade'
            )}
          </Button>
        )}
      </CardContent>
    </Card>
  )
}

function InvoiceRow({ invoice }: { invoice: InvoiceResponse }) {
  const statusColors: Record<string, string> = {
    paid: 'bg-green-100 text-green-800',
    open: 'bg-yellow-100 text-yellow-800',
    draft: 'bg-gray-100 text-gray-800',
    void: 'bg-red-100 text-red-800',
    uncollectible: 'bg-red-100 text-red-800',
  }

  return (
    <div className="flex items-center justify-between py-3 border-b last:border-0">
      <div className="flex items-center gap-3">
        <Receipt className="h-4 w-4 text-muted-foreground" />
        <div>
          <p className="font-medium text-sm">
            {invoice.invoice_number || invoice.id.slice(0, 8)}
          </p>
          <p className="text-xs text-muted-foreground">{formatDate(invoice.created_at)}</p>
        </div>
      </div>
      <div className="flex items-center gap-4">
        <span className={cn('px-2 py-0.5 rounded text-xs font-medium', statusColors[invoice.status])}>
          {invoice.status}
        </span>
        <span className="font-medium">{formatCurrency(invoice.total, invoice.currency)}</span>
        <div className="flex gap-1">
          {invoice.hosted_invoice_url && (
            <Button variant="ghost" size="icon" asChild>
              <a href={invoice.hosted_invoice_url} target="_blank" rel="noopener noreferrer">
                <ExternalLink className="h-4 w-4" />
              </a>
            </Button>
          )}
          {invoice.invoice_pdf && (
            <Button variant="ghost" size="icon" asChild>
              <a href={invoice.invoice_pdf} target="_blank" rel="noopener noreferrer">
                <Download className="h-4 w-4" />
              </a>
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}

function PaymentMethodCard({
  paymentMethod,
  onDelete,
}: {
  paymentMethod: PaymentMethodResponse
  onDelete: () => void
}) {
  const [isDeleting, setIsDeleting] = useState(false)

  const handleDelete = async () => {
    setIsDeleting(true)
    await onDelete()
    setIsDeleting(false)
  }

  return (
    <div className="flex items-center justify-between p-3 border rounded-lg">
      <div className="flex items-center gap-3">
        <CreditCard className="h-5 w-5 text-muted-foreground" />
        <div>
          <p className="font-medium text-sm">
            {paymentMethod.card_brand?.toUpperCase()} **** {paymentMethod.card_last4}
          </p>
          <p className="text-xs text-muted-foreground">
            Expires {paymentMethod.card_exp_month}/{paymentMethod.card_exp_year}
          </p>
        </div>
        {paymentMethod.is_default && (
          <span className="text-xs bg-primary/10 text-primary px-2 py-0.5 rounded">Default</span>
        )}
      </div>
      {!paymentMethod.is_default && (
        <Button
          variant="ghost"
          size="icon"
          onClick={handleDelete}
          disabled={isDeleting}
          className="text-destructive hover:text-destructive"
        >
          {isDeleting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
        </Button>
      )}
    </div>
  )
}

function UsageBar({ label, used, limit }: { label: string; used: number; limit: number }) {
  const isUnlimited = limit === -1
  const percentage = isUnlimited ? 0 : Math.min((used / limit) * 100, 100)
  const isNearLimit = percentage >= 80

  return (
    <div className="space-y-1">
      <div className="flex justify-between text-sm">
        <span>{label}</span>
        <span className={cn(isNearLimit && !isUnlimited && 'text-yellow-600 font-medium')}>
          {used.toLocaleString()} / {isUnlimited ? 'Unlimited' : limit.toLocaleString()}
        </span>
      </div>
      {!isUnlimited && (
        <div className="h-2 bg-muted rounded-full overflow-hidden">
          <div
            className={cn(
              'h-full rounded-full transition-all',
              isNearLimit ? 'bg-yellow-500' : 'bg-primary'
            )}
            style={{ width: `${percentage}%` }}
          />
        </div>
      )}
    </div>
  )
}

export default function BillingPage() {
  const { toast } = useToast()
  const [isLoading, setIsLoading] = useState(true)
  const [subscription, setSubscription] = useState<SubscriptionResponse | null>(null)
  const [plans, setPlans] = useState<PlanInfo[]>([])
  const [invoices, setInvoices] = useState<InvoiceResponse[]>([])
  const [paymentMethods, setPaymentMethods] = useState<PaymentMethodResponse[]>([])
  const [usage, setUsage] = useState<UsageSummaryResponse | null>(null)
  const [billingCycle, setBillingCycle] = useState<'monthly' | 'yearly'>('monthly')
  const [isCheckingOut, setIsCheckingOut] = useState(false)

  useEffect(() => {
    loadBillingData()
  }, [])

  const loadBillingData = async () => {
    try {
      setIsLoading(true)
      const [subData, plansData, invoicesData, pmData, usageData] = await Promise.all([
        billingApi.getSubscription(),
        billingApi.getPlans(),
        billingApi.getInvoices(),
        billingApi.getPaymentMethods(),
        billingApi.getUsage(),
      ])
      setSubscription(subData)
      setPlans(plansData.plans)
      setInvoices(invoicesData.invoices)
      setPaymentMethods(pmData)
      setUsage(usageData)
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to load billing information',
        variant: 'destructive',
      })
    } finally {
      setIsLoading(false)
    }
  }

  const handleSelectPlan = async (priceId: string) => {
    setIsCheckingOut(true)
    try {
      const { checkout_url } = await billingApi.createCheckout({
        price_id: priceId,
        success_url: `${window.location.origin}/settings/billing?success=true`,
        cancel_url: `${window.location.origin}/settings/billing?canceled=true`,
      })
      window.location.href = checkout_url
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to start checkout process',
        variant: 'destructive',
      })
      setIsCheckingOut(false)
    }
  }

  const handleManageBilling = async () => {
    try {
      const { portal_url } = await billingApi.createPortalSession(window.location.href)
      window.location.href = portal_url
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to open billing portal',
        variant: 'destructive',
      })
    }
  }

  const handleDeletePaymentMethod = async (paymentMethodId: string) => {
    try {
      await billingApi.deletePaymentMethod(paymentMethodId)
      setPaymentMethods((prev) => prev.filter((pm) => pm.id !== paymentMethodId))
      toast({
        title: 'Payment method removed',
        description: 'The payment method has been removed from your account.',
      })
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to remove payment method',
        variant: 'destructive',
      })
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  const currentPlan = subscription?.plan_tier || 'free'
  const isSubscribed = subscription && subscription.id !== 'free'

  return (
    <div className="space-y-6">
      {/* Current Plan */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Package className="h-5 w-5" />
              <CardTitle>Current Plan</CardTitle>
            </div>
            {isSubscribed && (
              <Button variant="outline" size="sm" onClick={handleManageBilling}>
                <Settings className="h-4 w-4 mr-2" />
                Manage Billing
              </Button>
            )}
          </div>
          <CardDescription>Manage your subscription and billing</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between p-4 bg-muted rounded-lg">
            <div>
              <p className="font-semibold text-lg capitalize">{currentPlan} Plan</p>
              <p className="text-sm text-muted-foreground">
                {subscription?.status === 'active' && 'Active subscription'}
                {subscription?.status === 'trialing' && 'Trial period'}
                {subscription?.status === 'canceled' && 'Canceled'}
                {subscription?.cancel_at_period_end && (
                  <span className="text-yellow-600">
                    {' '}
                    - Cancels on {formatDate(subscription.current_period_end)}
                  </span>
                )}
                {!isSubscribed && 'Free tier'}
              </p>
              {subscription?.current_period_end && !subscription.cancel_at_period_end && (
                <p className="text-xs text-muted-foreground mt-1">
                  Renews on {formatDate(subscription.current_period_end)}
                </p>
              )}
            </div>
            {!isSubscribed && (
              <Button onClick={() => document.getElementById('plans')?.scrollIntoView({ behavior: 'smooth' })}>
                <Zap className="h-4 w-4 mr-2" />
                Upgrade
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Usage */}
      {usage && (
        <Card>
          <CardHeader>
            <CardTitle>Current Usage</CardTitle>
            <CardDescription>Your usage this billing period</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <UsageBar
              label="AI Generations"
              used={usage.usage.ai_generation || 0}
              limit={usage.limits.ai_generations}
            />
            <UsageBar
              label="API Requests"
              used={usage.usage.api_request || 0}
              limit={usage.limits.api_requests_per_day}
            />
            <UsageBar
              label="Report Exports"
              used={usage.usage.report_export || 0}
              limit={usage.limits.report_exports}
            />
          </CardContent>
        </Card>
      )}

      {/* Available Plans */}
      <div id="plans">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold">Available Plans</h3>
          <div className="flex items-center gap-2 p-1 bg-muted rounded-lg">
            <Button
              variant={billingCycle === 'monthly' ? 'default' : 'ghost'}
              size="sm"
              onClick={() => setBillingCycle('monthly')}
            >
              Monthly
            </Button>
            <Button
              variant={billingCycle === 'yearly' ? 'default' : 'ghost'}
              size="sm"
              onClick={() => setBillingCycle('yearly')}
            >
              Yearly
              <span className="ml-1 text-xs bg-green-100 text-green-800 px-1.5 py-0.5 rounded">
                Save 17%
              </span>
            </Button>
          </div>
        </div>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {plans.map((plan) => (
            <PlanCard
              key={plan.id}
              plan={plan}
              currentPlan={currentPlan}
              billingCycle={billingCycle}
              onSelect={handleSelectPlan}
              isLoading={isCheckingOut}
            />
          ))}
        </div>
      </div>

      {/* Payment Methods */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <CreditCard className="h-5 w-5" />
            <CardTitle>Payment Methods</CardTitle>
          </div>
          <CardDescription>Manage your payment details</CardDescription>
        </CardHeader>
        <CardContent>
          {paymentMethods.length > 0 ? (
            <div className="space-y-2">
              {paymentMethods.map((pm) => (
                <PaymentMethodCard
                  key={pm.id}
                  paymentMethod={pm}
                  onDelete={() => handleDeletePaymentMethod(pm.id)}
                />
              ))}
              <Button variant="outline" className="mt-2" onClick={handleManageBilling}>
                Add Payment Method
              </Button>
            </div>
          ) : (
            <div className="text-sm text-muted-foreground">
              <p>No payment method on file.</p>
              {isSubscribed ? (
                <Button variant="link" className="px-0" onClick={handleManageBilling}>
                  Add a payment method
                </Button>
              ) : (
                <p className="text-xs mt-1">A payment method will be added when you upgrade.</p>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Billing History */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Receipt className="h-5 w-5" />
            <CardTitle>Billing History</CardTitle>
          </div>
          <CardDescription>View and download your invoices</CardDescription>
        </CardHeader>
        <CardContent>
          {invoices.length > 0 ? (
            <div>
              {invoices.map((invoice) => (
                <InvoiceRow key={invoice.id} invoice={invoice} />
              ))}
            </div>
          ) : (
            <div className="text-sm text-muted-foreground">No invoices yet.</div>
          )}
        </CardContent>
      </Card>

      {/* Info Card */}
      <Card className="bg-muted/50">
        <CardContent className="pt-6">
          <div className="flex items-start gap-3">
            <AlertCircle className="h-5 w-5 text-muted-foreground mt-0.5" />
            <div className="text-sm text-muted-foreground">
              <p className="font-medium mb-1">Secure Payments</p>
              <p>
                All payments are processed securely through Stripe. We never store your card
                details on our servers.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
