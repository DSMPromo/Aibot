import { useEffect, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { AlertCircle, CheckCircle2, Loader2 } from 'lucide-react'

import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { useConnectionsStore } from '@/stores/connections'

type CallbackStatus = 'loading' | 'success' | 'error' | 'selecting'

export default function OAuthCallbackPage() {
  const { platform } = useParams<{ platform: string }>()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const { pendingOAuth, setPendingOAuth, fetchConnections } = useConnectionsStore()

  const [status, setStatus] = useState<CallbackStatus>('loading')
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  useEffect(() => {
    const handleCallback = async () => {
      const code = searchParams.get('code')
      const state = searchParams.get('state')
      const error = searchParams.get('error')
      const errorDescription = searchParams.get('error_description')

      // Check for OAuth errors
      if (error) {
        setStatus('error')
        setErrorMessage(errorDescription || error)
        return
      }

      // Validate required params
      if (!code || !state) {
        setStatus('error')
        setErrorMessage('Missing authorization code or state parameter')
        return
      }

      // Validate state matches (CSRF protection)
      if (pendingOAuth && pendingOAuth.state !== state) {
        setStatus('error')
        setErrorMessage('Invalid state parameter. Please try again.')
        return
      }

      try {
        // The backend handles the token exchange via the callback endpoint
        // This page is typically opened in a popup, so we communicate back to the opener

        // For now, show success and redirect
        setStatus('success')

        // Refresh connections list
        await fetchConnections()

        // Clear pending OAuth state
        setPendingOAuth(null)

        // If in a popup, close it and refresh the parent
        if (window.opener) {
          window.opener.postMessage({ type: 'oauth_success', platform }, '*')
          window.close()
        } else {
          // If not in popup, redirect to connections page after delay
          setTimeout(() => {
            navigate('/settings/connections')
          }, 2000)
        }
      } catch (err) {
        setStatus('error')
        setErrorMessage(err instanceof Error ? err.message : 'Failed to complete authorization')
      }
    }

    handleCallback()
  }, [searchParams, platform, pendingOAuth, setPendingOAuth, fetchConnections, navigate])

  const handleRetry = () => {
    navigate('/settings/connections')
  }

  const handleClose = () => {
    if (window.opener) {
      window.close()
    } else {
      navigate('/settings/connections')
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-gray-50">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <CardTitle>
            {status === 'loading' && 'Connecting...'}
            {status === 'success' && 'Connected!'}
            {status === 'error' && 'Connection Failed'}
            {status === 'selecting' && 'Select Accounts'}
          </CardTitle>
          <CardDescription>
            {platform?.charAt(0).toUpperCase()}{platform?.slice(1)} Ads
          </CardDescription>
        </CardHeader>

        <CardContent className="flex flex-col items-center gap-4">
          {status === 'loading' && (
            <>
              <Loader2 className="h-12 w-12 animate-spin text-primary" />
              <p className="text-muted-foreground text-center">
                Completing authorization...
              </p>
            </>
          )}

          {status === 'success' && (
            <>
              <div className="h-16 w-16 rounded-full bg-green-100 flex items-center justify-center">
                <CheckCircle2 className="h-8 w-8 text-green-600" />
              </div>
              <p className="text-center">
                Your {platform} account has been connected successfully.
              </p>
              <p className="text-sm text-muted-foreground text-center">
                Redirecting to connections...
              </p>
            </>
          )}

          {status === 'error' && (
            <>
              <div className="h-16 w-16 rounded-full bg-red-100 flex items-center justify-center">
                <AlertCircle className="h-8 w-8 text-red-600" />
              </div>
              <p className="text-center text-destructive">{errorMessage}</p>
              <div className="flex gap-2">
                <Button variant="outline" onClick={handleClose}>
                  Close
                </Button>
                <Button onClick={handleRetry}>Try Again</Button>
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
