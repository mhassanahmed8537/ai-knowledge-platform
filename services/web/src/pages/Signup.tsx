import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ApiError } from '@/api/client'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { useAuth } from '@/context/AuthContext'
import { AuthLayout } from './AuthLayout'

export function Signup() {
  const { signup } = useAuth()
  const navigate = useNavigate()
  const [orgName, setOrgName] = useState('')
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      await signup({ org_name: orgName, email, password, full_name: fullName || null })
      navigate('/chat', { replace: true })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthLayout title="Create your organization" subtitle="You'll be the first admin — invite your team afterwards.">
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <Input
          label="Organization name"
          name="org_name"
          required
          value={orgName}
          onChange={(e) => setOrgName(e.target.value)}
          placeholder="Acme Inc."
        />
        <Input
          label="Your name"
          name="full_name"
          value={fullName}
          onChange={(e) => setFullName(e.target.value)}
          placeholder="Optional"
        />
        <Input
          label="Email"
          type="email"
          name="email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <Input
          label="Password"
          type="password"
          name="password"
          autoComplete="new-password"
          required
          minLength={8}
          hint="At least 8 characters"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        {error && (
          <p role="alert" className="rounded-lg bg-danger-500/10 px-3 py-2 text-sm text-danger-500">
            {error}
          </p>
        )}
        <Button type="submit" size="lg" loading={loading} className="mt-2 w-full justify-center">
          Create organization
        </Button>
      </form>
      <p className="mt-6 text-center text-sm text-text-muted">
        Already have an account?{' '}
        <Link to="/login" className="font-medium text-brand-600 hover:underline dark:text-brand-300">
          Sign in
        </Link>
      </p>
    </AuthLayout>
  )
}
