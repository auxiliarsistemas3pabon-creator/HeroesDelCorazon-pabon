import { ClipboardList, List, ListPlus, LayoutDashboard, LogOut, Menu, Trophy, User, Users, X } from 'lucide-react'
import { useState } from 'react'
import { Link, NavLink, Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { cn } from '../lib/cn'
import { Button } from './ui/Button'

// Menú lateral por rol (`user.role`: 'boss' | 'superadmin' | 'collaborator'). Es solo navegación: el control
// real de acceso lo hace el backend; ocultar un enlace aquí no protege la ruta.
const BOSS_LINKS = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/results', label: 'Resultados', icon: Trophy },
  { to: '/create', label: 'Crear Evaluacion', icon: ListPlus },
  { to: '/program', label: 'Programar evaluación', icon: ListPlus },
  { to: '/evaluations-list', label: 'Lista de evaluaciones', icon: List },
]

const LINKS = {
  boss: BOSS_LINKS,
  // El superadmin hace todo lo del jefe y además carga datos (personal y evaluaciones).
  superadmin: [...BOSS_LINKS, { to: '/staff', label: 'Cargar datos', icon: Users }],
  collaborator: [
    { to: '/evaluations', label: 'Evaluar', icon: ClipboardList },
  ],
}

const ROLE_LABELS = { boss: 'Coordinador', superadmin: 'Administrador', collaborator: 'Colaborador' }

// Layout de todas las páginas autenticadas: cabecera, menú lateral y <Outlet/> con la página activa.
// Actúa también de guardia de sesión (ver redirecciones abajo).
export function Layout() {
  const { user, loading, logout } = useAuth()
  const [open, setOpen] = useState(false)

  // Mientras AuthContext consulta /auth/me/ no se redirige: evitaría un rebote a /login en cada recarga.
  if (loading) return null
  if (!user) return <Navigate to="/login" replace />
  // Contraseña temporal (p. ej. recién cargada desde el Excel de personal): obliga a cambiarla antes de usar la app.
  if (user.password_change_required) return <Navigate to="/change-password" replace />


  return (
    <div className="flex min-h-dvh flex-col bg-app">
      <header className="sticky top-0 z-30 border-b border-app bg-surface/90 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-screen-2xl items-center justify-between gap-3 px-4 sm:px-6">
          <div className="flex items-center gap-3">
            <button
              type="button"
              className="inline-flex h-10 w-10 items-center justify-center rounded-lg text-app hover:bg-app-muted lg:hidden"
              onClick={() => setOpen(true)}
              aria-label="Abrir menú"
            >
              <Menu size={20} />
            </button>
            <Link to="/" className="flex items-center gap-2">
              <div className="rounded-md bg-white p-1 shadow-sm">
                <img src="/icons/logo-clinica.png" alt="Clínica Pabón" className="h-9 w-auto" />
              </div>
              <div className="hidden flex-col leading-tight sm:flex">
                <span className="text-sm font-semibold text-app">Clínica Pabón</span>
                <span className="text-xs text-app-muted">Héroes del Corazón</span>
              </div>
            </Link>
          </div>

          <div className="flex items-center gap-2 sm:gap-3">
            <div className="hidden items-center gap-2 rounded-lg border border-app bg-app-muted px-3 py-2 sm:flex">
              <User size={16} className="text-app-muted" />
              <span className="text-sm font-medium text-app">{user.first_name} {user.last_name}</span>
              <span className="rounded bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
                {ROLE_LABELS[user.role]}
              </span>
            </div>
            <Button type="button" variant="secondary" size="sm" onClick={logout} leftIcon={<LogOut size={16} />}>
              <span className="hidden sm:inline">Salir</span>
            </Button>
          </div>
        </div>
      </header>

      <div className="flex min-w-0 flex-1">
        {open && <div className="fixed inset-0 z-30 bg-black/40 lg:hidden" onClick={() => setOpen(false)} aria-hidden />}
        <aside
          className={cn(
            'z-40 flex w-64 shrink-0 flex-col overflow-y-auto border-r border-app bg-surface',
            'fixed inset-y-0 left-0 transition-transform lg:sticky lg:top-16 lg:max-h-[calc(100dvh-4rem)] lg:translate-x-0 lg:self-start',
            open ? 'translate-x-0' : '-translate-x-full',
          )}
        >
          <div className="flex items-center justify-between border-b border-app px-4 py-3 lg:hidden">
            <span className="text-sm font-semibold text-app">Menú</span>
            <button
              type="button"
              className="inline-flex h-9 w-9 items-center justify-center rounded-lg text-app hover:bg-app-muted"
              onClick={() => setOpen(false)}
              aria-label="Cerrar menú"
            >
              <X size={18} />
            </button>
          </div>
          <nav className="flex flex-col gap-1 p-3">
            {LINKS[user.role].map(({ to, label, icon: Icon, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                onClick={() => setOpen(false)}
                className={({ isActive }) =>
                  cn(
                    'flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition',
                    isActive ? 'bg-primary/10 text-primary' : 'text-app hover:bg-app-muted',
                  )
                }
              >
                <Icon size={18} />
                <span>{label}</span>
              </NavLink>
            ))}
          </nav>
        </aside>

        <main className="min-w-0 flex-1 overflow-x-auto px-4 py-6 sm:px-6 lg:px-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
