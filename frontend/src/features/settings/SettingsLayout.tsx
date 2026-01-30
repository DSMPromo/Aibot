import { Link, Outlet, useLocation } from 'react-router-dom'
import { Link2, User, Shield, CreditCard, Bell } from 'lucide-react'

import { cn } from '@/lib/utils'

const settingsNav = [
  { name: 'Profile', href: '/settings/profile', icon: User },
  { name: 'Connections', href: '/settings/connections', icon: Link2 },
  { name: 'Alerts', href: '/settings/alerts', icon: Bell },
  { name: 'Security', href: '/settings/security', icon: Shield },
  { name: 'Billing', href: '/settings/billing', icon: CreditCard },
]

export default function SettingsLayout() {
  const location = useLocation()

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Settings</h1>
        <p className="text-muted-foreground">
          Manage your account settings and preferences
        </p>
      </div>

      <div className="flex flex-col gap-6 lg:flex-row">
        {/* Settings navigation */}
        <nav className="flex gap-2 lg:flex-col lg:w-48">
          {settingsNav.map((item) => {
            const isActive = location.pathname === item.href
            return (
              <Link
                key={item.name}
                to={item.href}
                className={cn(
                  'flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-primary text-primary-foreground'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                )}
              >
                <item.icon className="h-4 w-4" />
                {item.name}
              </Link>
            )
          })}
        </nav>

        {/* Settings content */}
        <div className="flex-1 min-w-0">
          <Outlet />
        </div>
      </div>
    </div>
  )
}
