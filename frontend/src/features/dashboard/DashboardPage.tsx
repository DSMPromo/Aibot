import {
  ArrowDownRight,
  ArrowUpRight,
  DollarSign,
  Eye,
  MousePointerClick,
  Target,
} from 'lucide-react'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { cn, formatCurrency, formatCompactNumber } from '@/lib/utils'

// Mock data - will be replaced with real API calls
const stats = [
  {
    name: 'Total Spend',
    value: 12560.5,
    change: 12.5,
    changeType: 'increase' as const,
    icon: DollarSign,
    format: 'currency' as const,
  },
  {
    name: 'Impressions',
    value: 2450000,
    change: 8.2,
    changeType: 'increase' as const,
    icon: Eye,
    format: 'compact' as const,
  },
  {
    name: 'Clicks',
    value: 48500,
    change: -3.1,
    changeType: 'decrease' as const,
    icon: MousePointerClick,
    format: 'compact' as const,
  },
  {
    name: 'Conversions',
    value: 1250,
    change: 15.3,
    changeType: 'increase' as const,
    icon: Target,
    format: 'compact' as const,
  },
]

const campaigns = [
  {
    id: 1,
    name: 'Summer Sale 2026',
    platform: 'Google',
    status: 'active',
    spend: 2340.5,
    impressions: 450000,
    clicks: 8500,
    conversions: 245,
  },
  {
    id: 2,
    name: 'Brand Awareness',
    platform: 'Meta',
    status: 'active',
    spend: 1890.0,
    impressions: 680000,
    clicks: 12300,
    conversions: 180,
  },
  {
    id: 3,
    name: 'Product Launch',
    platform: 'TikTok',
    status: 'paused',
    spend: 980.25,
    impressions: 320000,
    clicks: 5600,
    conversions: 95,
  },
]

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <p className="text-muted-foreground">
          Overview of your advertising performance
        </p>
      </div>

      {/* Stats grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat) => (
          <Card key={stat.name}>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                {stat.name}
              </CardTitle>
              <stat.icon className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {stat.format === 'currency'
                  ? formatCurrency(stat.value)
                  : formatCompactNumber(stat.value)}
              </div>
              <p
                className={cn(
                  'text-xs flex items-center gap-1',
                  stat.changeType === 'increase'
                    ? 'text-green-600'
                    : 'text-red-600'
                )}
              >
                {stat.changeType === 'increase' ? (
                  <ArrowUpRight className="h-3 w-3" />
                ) : (
                  <ArrowDownRight className="h-3 w-3" />
                )}
                {Math.abs(stat.change)}% from last month
              </p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Campaigns table */}
      <Card>
        <CardHeader>
          <CardTitle>Active Campaigns</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b text-left text-sm text-muted-foreground">
                  <th className="pb-3 font-medium">Campaign</th>
                  <th className="pb-3 font-medium">Platform</th>
                  <th className="pb-3 font-medium">Status</th>
                  <th className="pb-3 font-medium text-right">Spend</th>
                  <th className="pb-3 font-medium text-right">Impressions</th>
                  <th className="pb-3 font-medium text-right">Clicks</th>
                  <th className="pb-3 font-medium text-right">Conversions</th>
                </tr>
              </thead>
              <tbody>
                {campaigns.map((campaign) => (
                  <tr key={campaign.id} className="border-b last:border-0">
                    <td className="py-3 font-medium">{campaign.name}</td>
                    <td className="py-3">
                      <span
                        className={cn(
                          'inline-flex items-center rounded-full px-2 py-1 text-xs font-medium',
                          campaign.platform === 'Google' &&
                            'bg-blue-100 text-blue-700',
                          campaign.platform === 'Meta' &&
                            'bg-indigo-100 text-indigo-700',
                          campaign.platform === 'TikTok' &&
                            'bg-pink-100 text-pink-700'
                        )}
                      >
                        {campaign.platform}
                      </span>
                    </td>
                    <td className="py-3">
                      <span
                        className={cn(
                          'inline-flex items-center rounded-full px-2 py-1 text-xs font-medium',
                          campaign.status === 'active'
                            ? 'bg-green-100 text-green-700'
                            : 'bg-yellow-100 text-yellow-700'
                        )}
                      >
                        {campaign.status}
                      </span>
                    </td>
                    <td className="py-3 text-right">
                      {formatCurrency(campaign.spend)}
                    </td>
                    <td className="py-3 text-right">
                      {formatCompactNumber(campaign.impressions)}
                    </td>
                    <td className="py-3 text-right">
                      {formatCompactNumber(campaign.clicks)}
                    </td>
                    <td className="py-3 text-right">{campaign.conversions}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Quick actions */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card className="cursor-pointer hover:border-primary transition-colors">
          <CardContent className="flex items-center gap-4 p-6">
            <div className="h-12 w-12 rounded-lg bg-blue-100 flex items-center justify-center">
              <Target className="h-6 w-6 text-blue-600" />
            </div>
            <div>
              <h3 className="font-semibold">Create Campaign</h3>
              <p className="text-sm text-muted-foreground">
                Launch a new ad campaign
              </p>
            </div>
          </CardContent>
        </Card>

        <Card className="cursor-pointer hover:border-primary transition-colors">
          <CardContent className="flex items-center gap-4 p-6">
            <div className="h-12 w-12 rounded-lg bg-purple-100 flex items-center justify-center">
              <svg
                className="h-6 w-6 text-purple-600"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              >
                <path d="M12 2L2 7l10 5 10-5-10-5z" />
                <path d="M2 17l10 5 10-5" />
                <path d="M2 12l10 5 10-5" />
              </svg>
            </div>
            <div>
              <h3 className="font-semibold">Connect Account</h3>
              <p className="text-sm text-muted-foreground">
                Link Google, Meta, or TikTok
              </p>
            </div>
          </CardContent>
        </Card>

        <Card className="cursor-pointer hover:border-primary transition-colors">
          <CardContent className="flex items-center gap-4 p-6">
            <div className="h-12 w-12 rounded-lg bg-green-100 flex items-center justify-center">
              <svg
                className="h-6 w-6 text-green-600"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              >
                <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z" />
              </svg>
            </div>
            <div>
              <h3 className="font-semibold">Generate Ad Copy</h3>
              <p className="text-sm text-muted-foreground">
                Use AI to create content
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
