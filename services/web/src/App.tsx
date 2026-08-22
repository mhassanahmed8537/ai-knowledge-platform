import { Navigate, Route, BrowserRouter, Routes } from 'react-router-dom'
import { AppShell } from '@/layout/AppShell'
import { AdminRoute, ProtectedRoute } from '@/layout/ProtectedRoute'
import { ApiKeys } from '@/pages/ApiKeys'
import { Chat } from '@/pages/Chat'
import { Documents } from '@/pages/Documents'
import { Login } from '@/pages/Login'
import { Search } from '@/pages/Search'
import { Settings } from '@/pages/Settings'
import { Signup } from '@/pages/Signup'
import { Usage } from '@/pages/Usage'
import { Users } from '@/pages/Users'
import { Webhooks } from '@/pages/Webhooks'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/signup" element={<Signup />} />

        <Route element={<ProtectedRoute />}>
          <Route element={<AppShell />}>
            <Route path="/" element={<Navigate to="/chat" replace />} />
            <Route path="/chat" element={<Chat />} />
            <Route path="/chat/:conversationId" element={<Chat />} />
            <Route path="/documents" element={<Documents />} />
            <Route path="/search" element={<Search />} />
            <Route path="/usage" element={<Usage />} />
            <Route path="/webhooks" element={<Webhooks />} />
            <Route path="/api-keys" element={<ApiKeys />} />
            <Route path="/settings" element={<Settings />} />
            <Route element={<AdminRoute />}>
              <Route path="/users" element={<Users />} />
            </Route>
          </Route>
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
