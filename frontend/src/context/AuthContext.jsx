/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useEffect, useState } from 'react'
import { api } from '../lib/api'
import { connectRealtime } from '../lib/realtime'

// Sesión por cookies httpOnly: el front nunca ve los tokens, solo pregunta quién es el usuario.
const AuthContext = createContext(null)

// `user` es null sin sesión; `loading` es true hasta resolver el primer /auth/me/ (las rutas protegidas deben esperarlo).
// El objeto de usuario incluye `role` ('boss' | 'collaborator') y `password_change_required`.
export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  const [realtimeStatus, setRealtimeStatus] = useState('disconnected')
  const [realtimeEvent, setRealtimeEvent] = useState(null)
  const [realtimeNotice, setRealtimeNotice] = useState('')

  useEffect(() => {
    api('/auth/me/')
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (loading || !user || user.password_change_required) return undefined
    let noticeTimer
    const disconnect = connectRealtime({
      onStatus: setRealtimeStatus,
      onEvent: (event) => {
        setRealtimeEvent(event)
        const messages = {
          'questions.submitted': 'Se recibió una nueva evaluación.',
          'evaluations.updated': 'La programación de evaluaciones cambió.',
          'staff.updated': 'Se actualizó el personal.',
        }
        setRealtimeNotice(messages[event.type] || 'Hay una actualización en tiempo real.')
        window.clearTimeout(noticeTimer)
        noticeTimer = window.setTimeout(() => setRealtimeNotice(''), 5000)
      },
      refreshSession: async () => {
        try {
          await api('/auth/refresh/', { method: 'POST' })
          return true
        } catch {
          setUser(null)
          return false
        }
      },
    })
    return () => {
      disconnect()
      window.clearTimeout(noticeTimer)
    }
  }, [loading, user])

  async function login(credentials) {
    const data = await api('/auth/login/', { method: 'POST', body: credentials })
    setUser(data)
    return data
  }

  // Vuelve a pedir el usuario al backend, p. ej. tras cambiar la contraseña para limpiar password_change_required.
  async function refreshUser() {
    const data = await api('/auth/me/')
    setUser(data)
    return data
  }

  async function logout() {
    await api('/auth/logout/', { method: 'POST' })
    setUser(null)
  }

  return (
    <AuthContext.Provider
      value={{ user, loading, login, logout, refreshUser, realtimeStatus, realtimeEvent, realtimeNotice }}
    >
      {children}
    </AuthContext.Provider>
  )
}

// Solo funciona dentro de <AuthProvider>; fuera devuelve null y desestructurar fallaría.
export function useAuth() {
  return useContext(AuthContext)
}
