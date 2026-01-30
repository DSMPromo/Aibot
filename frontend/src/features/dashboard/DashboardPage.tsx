import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ArrowDownRight,
  ArrowUpRight,
  DollarSign,
  Eye,
  MousePointerClick,
  Target,
  TrendingUp,
  RefreshCw,
  Calendar,
  Loader2,
  Download,
  FileText,
  FileSpreadsheet,
} from 'lucide-react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts'
import { format, subDays } from 'date-fns'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { cn, formatCurrency, formatCompactNumber } from '@/lib/utils'
import {
  analyticsApi,
  exportsApi,
  downloadBlob,
  type MetricsComparison,
  type CampaignMetricsList,
  type TimeSeriesData,
  type PlatformComparisonResponse,
} from '@/lib/api'
import {
  BarChart,
  Bar,
  Cell,
  PieChart,
  Pie,
} from 'recharts'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'

type DateRange = '7d' | '14d' | '30d' | '90d'

const dateRangeOptions: { value: DateRange; label: string }[] = [
  { value: '7d', label: 'Last 7 days' },
  { value: '14d', label: 'Last 14 days' },
  { value: '30d', label: 'Last 30 days' },
  { value: '90d', label: 'Last 90 days' },
]

function getDateRangeDates(range: DateRange) {
  const end = new Date()
  const days = parseInt(range.replace('d', ''))
  const start = subDays(end, days)
  return {
    start_date: format(start, 'yyyy-MM-dd'),
    end_date: format(end, 'yyyy-MM-dd'),
  }
}

export default function DashboardPage() {
  const navigate = useNavigate()
  const [dateRange, setDateRange] = useState<DateRange>('30d')
  const [isLoading, setIsLoading] = useState(true)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [overview, setOverview] = useState<MetricsComparison | null>(null)
  const [campaigns, setCampaigns] = useState<CampaignMetricsList | null>(null)
  const [timeSeries, setTimeSeries] = useState<TimeSeriesData | null>(null)
  const [platformComparison, setPlatformComparison] = useState<PlatformComparisonResponse | null>(null)
  const [isExporting, setIsExporting] = useState(false)

  const handleExport = async (type: 'csv-overview' | 'csv-campaigns' | 'csv-timeseries' | 'pdf') => {
    setIsExporting(true)
    const dates = getDateRangeDates(dateRange)

    try {
      let blob: Blob
      let filename: string

      switch (type) {
        case 'csv-overview':
          blob = await exportsApi.downloadOverviewCsv(dates)
          filename = `overview_${dates.start_date}_${dates.end_date}.csv`
          break
        case 'csv-campaigns':
          blob = await exportsApi.downloadCampaignsCsv(dates)
          filename = `campaigns_${dates.start_date}_${dates.end_date}.csv`
          break
        case 'csv-timeseries':
          blob = await exportsApi.downloadTimeseriesCsv({ ...dates, granularity: 'daily' })
          filename = `timeseries_${dates.start_date}_${dates.end_date}.csv`
          break
        case 'pdf':
          blob = await exportsApi.downloadPdfReport({
            ...dates,
            title: 'Analytics Report',
          })
          filename = `report_${dates.start_date}_${dates.end_date}.pdf`
          break
      }

      downloadBlob(blob, filename)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to export')
    } finally {
      setIsExporting(false)
    }
  }

  const loadData = async (showLoading = true) => {
    if (showLoading) setIsLoading(true)
    else setIsRefreshing(true)

    setError(null)

    const dates = getDateRangeDates(dateRange)

    try {
      const [overviewData, campaignsData, timeSeriesData, platformData] = await Promise.all([
        analyticsApi.getOverview({
          ...dates,
          compare_previous: true,
        }),
        analyticsApi.getCampaignsList({
          ...dates,
          page_size: 10,
        }),
        analyticsApi.getTimeSeries({
          ...dates,
          granularity: dateRange === '7d' ? 'daily' : 'daily',
        }),
        analyticsApi.getPlatformComparison(dates),
      ])

      setOverview(overviewData)
      setCampaigns(campaignsData)
      setTimeSeries(timeSeriesData)
      setPlatformComparison(platformData)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load analytics data')
    } finally {
      setIsLoading(false)
      setIsRefreshing(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [dateRange])

  const stats = overview
    ? [
        {
          name: 'Total Spend',
          value: overview.current.spend,
          change: overview.change_percent.spend,
          icon: DollarSign,
          format: 'currency' as const,
        },
        {
          name: 'Impressions',
          value: overview.current.impressions,
          change: overview.change_percent.impressions,
          icon: Eye,
          format: 'compact' as const,
        },
        {
          name: 'Clicks',
          value: overview.current.clicks,
          change: overview.change_percent.clicks,
          icon: MousePointerClick,
          format: 'compact' as const,
        },
        {
          name: 'Conversions',
          value: overview.current.conversions,
          change: overview.change_percent.conversions,
          icon: Target,
          format: 'compact' as const,
        },
        {
          name: 'CTR',
          value: overview.current.ctr,
          change: overview.change_percent.ctr,
          icon: TrendingUp,
          format: 'percent' as const,
        },
        {
          name: 'ROAS',
          value: overview.current.roas,
          change: overview.change_percent.roas,
          icon: DollarSign,
          format: 'roas' as const,
        },
      ]
    : []

  const chartData = timeSeries?.data.map((point) => ({
    date: format(new Date(point.timestamp), 'MMM d'),
    spend: point.spend,
    impressions: point.impressions,
    clicks: point.clicks,
    conversions: point.conversions,
  })) || []

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-96 gap-4">
        <p className="text-destructive">{error}</p>
        <Button onClick={() => loadData()}>Retry</Button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Page header with controls */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Dashboard</h1>
          <p className="text-muted-foreground">
            Overview of your advertising performance
          </p>
        </div>
        <div className="flex items-center gap-2">
          {/* Date range selector */}
          <div className="flex items-center gap-1 rounded-lg border bg-background p-1">
            {dateRangeOptions.map((option) => (
              <button
                key={option.value}
                onClick={() => setDateRange(option.value)}
                className={cn(
                  'px-3 py-1.5 text-sm rounded-md transition-colors',
                  dateRange === option.value
                    ? 'bg-primary text-primary-foreground'
                    : 'hover:bg-muted'
                )}
              >
                {option.label}
              </button>
            ))}
          </div>

          {/* Export dropdown */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" disabled={isExporting}>
                {isExporting ? (
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                ) : (
                  <Download className="h-4 w-4 mr-2" />
                )}
                Export
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => handleExport('csv-overview')}>
                <FileSpreadsheet className="h-4 w-4 mr-2" />
                Overview CSV
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => handleExport('csv-campaigns')}>
                <FileSpreadsheet className="h-4 w-4 mr-2" />
                Campaigns CSV
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => handleExport('csv-timeseries')}>
                <FileSpreadsheet className="h-4 w-4 mr-2" />
                Time Series CSV
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => handleExport('pdf')}>
                <FileText className="h-4 w-4 mr-2" />
                Full Report (PDF)
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

          <Button
            variant="outline"
            size="icon"
            onClick={() => loadData(false)}
            disabled={isRefreshing}
          >
            <RefreshCw className={cn('h-4 w-4', isRefreshing && 'animate-spin')} />
          </Button>
        </div>
      </div>

      {/* Stats grid */}
      <div className="grid gap-4 md:grid-cols-3 lg:grid-cols-6">
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
                {stat.format === 'currency' && formatCurrency(stat.value)}
                {stat.format === 'compact' && formatCompactNumber(stat.value)}
                {stat.format === 'percent' && `${stat.value.toFixed(2)}%`}
                {stat.format === 'roas' && `${stat.value.toFixed(2)}x`}
              </div>
              {stat.change !== null && stat.change !== undefined && (
                <p
                  className={cn(
                    'text-xs flex items-center gap-1',
                    stat.change >= 0 ? 'text-green-600' : 'text-red-600'
                  )}
                >
                  {stat.change >= 0 ? (
                    <ArrowUpRight className="h-3 w-3" />
                  ) : (
                    <ArrowDownRight className="h-3 w-3" />
                  )}
                  {Math.abs(stat.change).toFixed(1)}% vs prev period
                </p>
              )}
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Chart */}
      <Card>
        <CardHeader>
          <CardTitle>Performance Over Time</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                <XAxis
                  dataKey="date"
                  className="text-xs text-muted-foreground"
                  tick={{ fill: 'currentColor' }}
                />
                <YAxis
                  yAxisId="left"
                  className="text-xs text-muted-foreground"
                  tick={{ fill: 'currentColor' }}
                  tickFormatter={(value) => formatCompactNumber(value)}
                />
                <YAxis
                  yAxisId="right"
                  orientation="right"
                  className="text-xs text-muted-foreground"
                  tick={{ fill: 'currentColor' }}
                  tickFormatter={(value) => `$${formatCompactNumber(value)}`}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'hsl(var(--background))',
                    border: '1px solid hsl(var(--border))',
                    borderRadius: '8px',
                  }}
                  formatter={(value: number, name: string) => {
                    if (name === 'spend') return [formatCurrency(value), 'Spend']
                    return [formatCompactNumber(value), name.charAt(0).toUpperCase() + name.slice(1)]
                  }}
                />
                <Legend />
                <Line
                  yAxisId="left"
                  type="monotone"
                  dataKey="impressions"
                  stroke="#3b82f6"
                  strokeWidth={2}
                  dot={false}
                />
                <Line
                  yAxisId="left"
                  type="monotone"
                  dataKey="clicks"
                  stroke="#8b5cf6"
                  strokeWidth={2}
                  dot={false}
                />
                <Line
                  yAxisId="right"
                  type="monotone"
                  dataKey="spend"
                  stroke="#10b981"
                  strokeWidth={2}
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      {/* Platform Comparison */}
      {platformComparison && Object.keys(platformComparison.platforms).length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Platform Performance Comparison</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {Object.entries(platformComparison.platforms).map(([platform, metrics]) => {
                const platformConfig = {
                  google: { color: '#4285F4', name: 'Google Ads' },
                  meta: { color: '#0668E1', name: 'Meta Ads' },
                  tiktok: { color: '#000000', name: 'TikTok Ads' },
                }[platform] || { color: '#888', name: platform }

                return (
                  <div
                    key={platform}
                    className="p-4 rounded-lg border"
                    style={{ borderLeftColor: platformConfig.color, borderLeftWidth: 4 }}
                  >
                    <div className="flex items-center justify-between mb-4">
                      <h4 className="font-semibold">{platformConfig.name}</h4>
                      <span className="text-sm text-muted-foreground">
                        {metrics.spend_share.toFixed(1)}% of spend
                      </span>
                    </div>
                    <div className="grid grid-cols-2 gap-3 text-sm">
                      <div>
                        <p className="text-muted-foreground">Spend</p>
                        <p className="font-medium">{formatCurrency(metrics.spend)}</p>
                      </div>
                      <div>
                        <p className="text-muted-foreground">ROAS</p>
                        <p className="font-medium">{metrics.roas.toFixed(2)}x</p>
                      </div>
                      <div>
                        <p className="text-muted-foreground">Conversions</p>
                        <p className="font-medium">{formatCompactNumber(metrics.conversions)}</p>
                      </div>
                      <div>
                        <p className="text-muted-foreground">CPA</p>
                        <p className="font-medium">{formatCurrency(metrics.cpa)}</p>
                      </div>
                      <div>
                        <p className="text-muted-foreground">CTR</p>
                        <p className="font-medium">{metrics.ctr.toFixed(2)}%</p>
                      </div>
                      <div>
                        <p className="text-muted-foreground">Campaigns</p>
                        <p className="font-medium">{metrics.campaign_count}</p>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Campaigns table */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Campaign Performance</CardTitle>
          <Button variant="outline" size="sm" onClick={() => navigate('/campaigns')}>
            View All
          </Button>
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
                  <th className="pb-3 font-medium text-right">CTR</th>
                  <th className="pb-3 font-medium text-right">Conversions</th>
                  <th className="pb-3 font-medium text-right">ROAS</th>
                </tr>
              </thead>
              <tbody>
                {campaigns?.campaigns.map((campaign) => (
                  <tr
                    key={campaign.campaign_id}
                    className="border-b last:border-0 cursor-pointer hover:bg-muted/50"
                    onClick={() => navigate(`/campaigns/${campaign.campaign_id}`)}
                  >
                    <td className="py-3 font-medium">{campaign.campaign_name}</td>
                    <td className="py-3">
                      <span
                        className={cn(
                          'inline-flex items-center rounded-full px-2 py-1 text-xs font-medium',
                          campaign.platform === 'google' && 'bg-blue-100 text-blue-700',
                          campaign.platform === 'meta' && 'bg-indigo-100 text-indigo-700',
                          campaign.platform === 'tiktok' && 'bg-pink-100 text-pink-700'
                        )}
                      >
                        {campaign.platform.charAt(0).toUpperCase() + campaign.platform.slice(1)}
                      </span>
                    </td>
                    <td className="py-3">
                      <span
                        className={cn(
                          'inline-flex items-center rounded-full px-2 py-1 text-xs font-medium',
                          campaign.status === 'active' && 'bg-green-100 text-green-700',
                          campaign.status === 'paused' && 'bg-yellow-100 text-yellow-700',
                          campaign.status === 'draft' && 'bg-gray-100 text-gray-700'
                        )}
                      >
                        {campaign.status}
                      </span>
                    </td>
                    <td className="py-3 text-right">
                      {formatCurrency(campaign.metrics.spend)}
                    </td>
                    <td className="py-3 text-right">
                      {formatCompactNumber(campaign.metrics.impressions)}
                    </td>
                    <td className="py-3 text-right">
                      {formatCompactNumber(campaign.metrics.clicks)}
                    </td>
                    <td className="py-3 text-right">
                      {campaign.metrics.ctr.toFixed(2)}%
                    </td>
                    <td className="py-3 text-right">{campaign.metrics.conversions}</td>
                    <td className="py-3 text-right">{campaign.metrics.roas.toFixed(2)}x</td>
                  </tr>
                ))}
                {(!campaigns || campaigns.campaigns.length === 0) && (
                  <tr>
                    <td colSpan={9} className="py-8 text-center text-muted-foreground">
                      No campaigns found. Create your first campaign to see metrics.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Quick actions */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card
          className="cursor-pointer hover:border-primary transition-colors"
          onClick={() => navigate('/campaigns/new')}
        >
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

        <Card
          className="cursor-pointer hover:border-primary transition-colors"
          onClick={() => navigate('/settings/connections')}
        >
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
              <Calendar className="h-6 w-6 text-green-600" />
            </div>
            <div>
              <h3 className="font-semibold">Schedule Report</h3>
              <p className="text-sm text-muted-foreground">
                Set up automated reports
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
