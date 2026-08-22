// Access + refresh tokens live in localStorage so a page reload doesn't log
// the user out. A tiny pub-sub lets React (AuthContext) react to changes
// made outside of React state (e.g. a silent refresh from the fetch client).

const ACCESS_KEY = 'kp_access_token'
const REFRESH_KEY = 'kp_refresh_token'

type Listener = () => void
const listeners = new Set<Listener>()

function notify() {
  for (const l of listeners) l()
}

export const tokenStore = {
  getAccessToken(): string | null {
    return localStorage.getItem(ACCESS_KEY)
  },
  getRefreshToken(): string | null {
    return localStorage.getItem(REFRESH_KEY)
  },
  setTokens(accessToken: string, refreshToken: string) {
    localStorage.setItem(ACCESS_KEY, accessToken)
    localStorage.setItem(REFRESH_KEY, refreshToken)
    notify()
  },
  clear() {
    localStorage.removeItem(ACCESS_KEY)
    localStorage.removeItem(REFRESH_KEY)
    notify()
  },
  subscribe(listener: Listener): () => void {
    listeners.add(listener)
    return () => listeners.delete(listener)
  },
}
