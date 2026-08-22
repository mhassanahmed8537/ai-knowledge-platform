import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import { PageSpinner } from '@/components/ui/Spinner'

export function ProtectedRoute() {
  const { status } = useAuth()
  const location = useLocation()

  if (status === 'loading') return <PageSpinner />
  if (status === 'anonymous') {
    return <Navigate to="/login" state={{ from: location }} replace />
  }
  return <Outlet />
}

export function AdminRoute() {
  const { user, status } = useAuth()
  if (status === 'loading') return <PageSpinner />
  if (user?.role !== 'admin') return <Navigate to="/" replace />
  return <Outlet />
}
