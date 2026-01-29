import { Outlet } from 'react-router-dom'

export default function AuthLayout() {
  return (
    <div className="min-h-screen flex">
      {/* Left side - Branding */}
      <div className="hidden lg:flex lg:w-1/2 bg-primary items-center justify-center p-12">
        <div className="max-w-md text-white">
          <h1 className="text-4xl font-bold mb-6">AI Marketing Platform</h1>
          <p className="text-xl text-primary-foreground/80 mb-8">
            Manage your Google, Meta, and TikTok ads from one dashboard.
            Let AI generate your ad copy and optimize your campaigns.
          </p>
          <div className="space-y-4">
            <Feature text="Unified dashboard for all ad platforms" />
            <Feature text="AI-powered ad copy generation" />
            <Feature text="Automated rules and optimization" />
            <Feature text="Real-time analytics and reporting" />
          </div>
        </div>
      </div>

      {/* Right side - Auth forms */}
      <div className="w-full lg:w-1/2 flex items-center justify-center p-8">
        <div className="w-full max-w-md">
          <Outlet />
        </div>
      </div>
    </div>
  )
}

function Feature({ text }: { text: string }) {
  return (
    <div className="flex items-center gap-3">
      <div className="h-2 w-2 rounded-full bg-white/80" />
      <span className="text-primary-foreground/90">{text}</span>
    </div>
  )
}
