import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { AuthProvider, useAuth } from './context/AuthContext'
import { DashboardPage } from './pages/DashboardPage'
import { EvaluationPage } from './pages/EvaluationPage'
import { EvaluationsListPage } from './pages/EvaluationsListPage'
import { FormCreatePage } from './pages/FormCreatePage';
import { FormProgramPage } from './pages/FormProgramPage';
import { LoginPage } from './pages/LoginPage'
import { PasswordChangePage } from './pages/PasswordChangePage'
import { ResultsPage } from './pages/ResultsPage'
import { StaffImportPage } from './pages/StaffImportPage'

// Destino de "/": roles `boss`/`superadmin` -> dashboard; los demás -> evaluar.
// El dashboard es solo del jefe; el colaborador entra directo a evaluar.
function Home() {
  const { user } = useAuth()
  return user.role === 'boss' || user.role === 'superadmin' ? <DashboardPage /> : <Navigate to="/evaluations" replace />
}

function StaffRoute() {
  const { user } = useAuth()
  return user.role === 'superadmin' ? <StaffImportPage /> : <Navigate to="/" replace />
}

// Rutas: /login y /change-password van fuera de <Layout>; el resto se renderiza dentro de Layout, que exige sesión
// y define el menú por rol. Ocultar un enlace NO protege la ruta: los permisos reales los aplica el backend.
function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        {/* AuthProvider dentro del Router para poder usar navegación; consulta /auth/me/ al iniciar */}
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/change-password" element={<PasswordChangePage />} />
          <Route element={<Layout />}>
            <Route path="/" element={<Home />} />
            <Route path="/evaluations" element={<EvaluationPage />} />
            <Route path="/results" element={<ResultsPage />} />
            <Route path="/evaluations-list" element={<EvaluationsListPage />} />
            <Route path="/create" element={<FormCreatePage />} />
            <Route path="/program" element={<FormProgramPage/>} />
            {/* Solo el superadmin carga datos; el backend lo exige igualmente */}
            <Route path="/staff" element={<StaffRoute />} />
            {/* Cualquier ruta desconocida vuelve a Home, que decide según el rol */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}

export default App
