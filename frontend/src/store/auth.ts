import { create } from 'zustand'

interface User {
  id: string
  email: string
}

interface AuthState {
  token: string | null
  user: User | null
  setAuth: (token: string, user: User) => void
  clearAuth: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  token: localStorage.getItem('token'),
  user: null,
  setAuth: (token, user) => {
    localStorage.setItem('token', token)
    set({ token, user })
  },
  clearAuth: () => {
    localStorage.removeItem('token')
    set({ token: null, user: null })
  },
}))
