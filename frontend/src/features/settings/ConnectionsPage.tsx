import { useEffect, useState } from 'react'
import {
  AlertCircle,
  CheckCircle2,
  ExternalLink,
  Loader2,
  RefreshCw,
  Trash2,
  Unplug,
} from 'lucide-react'

import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { useConnectionsStore } from '@/stores/connections'
import { useToast } from '@/hooks/use-toast'
import { cn } from '@/lib/utils'
import type { AdAccountResponse } from '@/lib/api'

// Platform configuration
const platforms = [
  {
    id: 'google' as const,
    name: 'Google Ads',
    description: 'Connect your Google Ads account to manage campaigns',
    icon: 'G',
    color: 'bg-blue-500',
    textColor: 'text-white',
    available: true,
  },
  {
    id: 'meta' as const,
    name: 'Meta Ads',
    description: 'Connect Facebook and Instagram advertising',
    icon: 'M',
    color: 'bg-gradient-to-r from-blue-500 to-purple-500',
    textColor: 'text-white',
    available: true,
  },
  {
    id: 'tiktok' as const,
    name: 'TikTok Ads',
    description: 'Connect your TikTok for Business account',
    icon: 'T',
    color: 'bg-black',
    textColor: 'text-white',
    available: true,
  },
]

function PlatformIcon({ platform, className }: { platform: string; className?: string }) {
  const config = platforms.find((p) => p.id === platform)
  return (
    <div className={cn('h-10 w-10 rounded-lg flex items-center justify-center text-white font-bold', config?.color || 'bg-gray-500', className)}>
      {platform.charAt(0).toUpperCase()}
    </div>
  )
}

function SyncStatusBadge({ status }: { status: AdAccountResponse['sync_status'] }) {
  const config = {
    pending: { label: 'Pending', color: 'bg-yellow-100 text-yellow-800' },
    syncing: { label: 'Syncing...', color: 'bg-blue-100 text-blue-800' },
    success: { label: 'Synced', color: 'bg-green-100 text-green-800' },
    error: { label: 'Error', color: 'bg-red-100 text-red-800' },
    auth_error: { label: 'Auth Error', color: 'bg-red-100 text-red-800' },
  }

  const { label, color } = config[status]

  return (
    <span className={cn('inline-flex items-center px-2 py-0.5 rounded text-xs font-medium', color)}>
      {status === 'syncing' && <Loader2 className="h-3 w-3 mr-1 animate-spin" />}
      {status === 'success' && <CheckCircle2 className="h-3 w-3 mr-1" />}
      {(status === 'error' || status === 'auth_error') && <AlertCircle className="h-3 w-3 mr-1" />}
      {label}
    </span>
  )
}

function ConnectedAccount({
  account,
  onDisconnect,
  onSync,
  onRefresh,
}: {
  account: AdAccountResponse
  onDisconnect: () => void
  onSync: () => void
  onRefresh: () => void
}) {
  const [isDisconnecting, setIsDisconnecting] = useState(false)

  return (
    <div className="flex items-center gap-4 p-4 border rounded-lg">
      <PlatformIcon platform={account.platform} />

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <p className="font-medium truncate">
            {account.platform_account_name || account.platform_account_id}
          </p>
          <SyncStatusBadge status={account.sync_status} />
        </div>
        <p className="text-sm text-muted-foreground">
          ID: {account.platform_account_id}
        </p>
        {account.last_sync_at && (
          <p className="text-xs text-muted-foreground">
            Last synced: {new Date(account.last_sync_at).toLocaleString()}
          </p>
        )}
      </div>

      <div className="flex items-center gap-2">
        {account.needs_reauth ? (
          <Button
            variant="outline"
            size="sm"
            onClick={onRefresh}
            className="text-yellow-600 border-yellow-600 hover:bg-yellow-50"
          >
            <RefreshCw className="h-4 w-4 mr-1" />
            Reconnect
          </Button>
        ) : (
          <Button variant="outline" size="icon" onClick={onSync} title="Sync now">
            <RefreshCw className="h-4 w-4" />
          </Button>
        )}

        <Button
          variant="outline"
          size="icon"
          onClick={() => {
            setIsDisconnecting(true)
            onDisconnect()
          }}
          disabled={isDisconnecting}
          className="text-destructive hover:bg-destructive hover:text-destructive-foreground"
          title="Disconnect"
        >
          {isDisconnecting ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Unplug className="h-4 w-4" />
          )}
        </Button>
      </div>
    </div>
  )
}

function PlatformCard({
  platform,
  connectedAccounts,
  onConnect,
  isConnecting,
}: {
  platform: typeof platforms[0]
  connectedAccounts: AdAccountResponse[]
  onConnect: () => void
  isConnecting: boolean
}) {
  const { disconnectAccount, triggerSync, refreshToken } = useConnectionsStore()
  const { toast } = useToast()

  const handleDisconnect = async (accountId: string) => {
    try {
      await disconnectAccount(accountId)
      toast({
        title: 'Account disconnected',
        description: 'The ad account has been disconnected.',
      })
    } catch {
      toast({
        title: 'Error',
        description: 'Failed to disconnect account.',
        variant: 'destructive',
      })
    }
  }

  const handleSync = async (accountId: string) => {
    try {
      await triggerSync(accountId)
      toast({
        title: 'Sync started',
        description: 'Data sync has been queued.',
      })
    } catch {
      toast({
        title: 'Error',
        description: 'Failed to start sync.',
        variant: 'destructive',
      })
    }
  }

  const handleRefresh = async (accountId: string) => {
    try {
      await refreshToken(accountId)
      toast({
        title: 'Token refreshed',
        description: 'Authentication has been refreshed.',
      })
    } catch {
      toast({
        title: 'Error',
        description: 'Failed to refresh token. Try reconnecting.',
        variant: 'destructive',
      })
    }
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-4">
          <PlatformIcon platform={platform.id} />
          <div className="flex-1">
            <CardTitle className="text-lg">{platform.name}</CardTitle>
            <CardDescription>{platform.description}</CardDescription>
          </div>
          {platform.available ? (
            <Button onClick={onConnect} disabled={isConnecting}>
              {isConnecting ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Connecting...
                </>
              ) : connectedAccounts.length > 0 ? (
                'Add Account'
              ) : (
                'Connect'
              )}
            </Button>
          ) : (
            <span className="text-sm text-muted-foreground px-3 py-1 bg-muted rounded-full">
              Coming Soon
            </span>
          )}
        </div>
      </CardHeader>

      {connectedAccounts.length > 0 && (
        <CardContent>
          <div className="space-y-3">
            {connectedAccounts.map((account) => (
              <ConnectedAccount
                key={account.id}
                account={account}
                onDisconnect={() => handleDisconnect(account.id)}
                onSync={() => handleSync(account.id)}
                onRefresh={() => handleRefresh(account.id)}
              />
            ))}
          </div>
        </CardContent>
      )}
    </Card>
  )
}

export default function ConnectionsPage() {
  const { accounts, isLoading, error, fetchConnections, initiateConnection, clearError } =
    useConnectionsStore()
  const { toast } = useToast()
  const [connectingPlatform, setConnectingPlatform] = useState<string | null>(null)

  useEffect(() => {
    fetchConnections()
  }, [fetchConnections])

  useEffect(() => {
    if (error) {
      toast({
        title: 'Error',
        description: error,
        variant: 'destructive',
      })
      clearError()
    }
  }, [error, toast, clearError])

  const handleConnect = async (platform: 'google' | 'meta' | 'tiktok') => {
    setConnectingPlatform(platform)
    try {
      const authUrl = await initiateConnection(platform)
      // Open OAuth flow in a new window
      window.open(authUrl, '_blank', 'width=600,height=700')
    } catch {
      // Error handled by store
    } finally {
      setConnectingPlatform(null)
    }
  }

  const getAccountsForPlatform = (platformId: string) =>
    accounts.filter((a) => a.platform === platformId)

  if (isLoading && accounts.length === 0) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold">Ad Platform Connections</h2>
        <p className="text-muted-foreground">
          Connect your advertising accounts to sync campaigns and analytics
        </p>
      </div>

      <div className="space-y-4">
        {platforms.map((platform) => (
          <PlatformCard
            key={platform.id}
            platform={platform}
            connectedAccounts={getAccountsForPlatform(platform.id)}
            onConnect={() => handleConnect(platform.id)}
            isConnecting={connectingPlatform === platform.id}
          />
        ))}
      </div>

      {/* OAuth callback info */}
      <Card className="bg-muted/50">
        <CardContent className="pt-6">
          <div className="flex items-start gap-3">
            <AlertCircle className="h-5 w-5 text-muted-foreground mt-0.5" />
            <div className="text-sm text-muted-foreground">
              <p className="font-medium mb-1">OAuth Authorization</p>
              <p>
                When you connect an account, you'll be redirected to the platform's
                authorization page. After granting access, you'll be able to select
                which ad accounts to sync.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
