/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useEffect, useState } from 'react'
import { api } from '../lib/api'

// Sesión por cookies httpOnly: el front nunca ve los tokens, solo pregunta quién es el usuario.
const AuthContext = createContext(null)

// `user` es null sin sesión; `loading` es true hasta resolver el primer /auth/me/ (las rutas protegidas deben esperarlo).
// El objeto de usuario incluye `role` ('boss' | 'collaborator') y `password_change_required`.
export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api('/auth/me/')
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setLoading(false))
  }, [])

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

  return <AuthContext.Provider value={{ user, loading, login, logout, refreshUser }}>{children}</AuthContext.Provider>
}

// Solo funciona dentro de <AuthProvider>; fuera devuelve null y desestructurar fallaría.
export function useAuth() {
  return useContext(AuthContext)
}
