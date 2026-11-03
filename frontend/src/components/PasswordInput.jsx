import { Eye, EyeOff } from 'lucide-react'
import { useState } from 'react'
import { cn } from '../lib/cn'
import { FIELD } from './ui/styles'

// Campo de contraseña con botón para mostrar u ocultar lo escrito.
// Acepta las props de un <input> (value, onChange, autoComplete...); `type` lo controla este componente.
export function PasswordInput({ className, ...props }) {
  const [visible, setVisible] = useState(false)

  return (
    <span className="relative block">
      <input {...props} type={visible ? 'text' : 'password'} className={cn(FIELD, 'pr-10', className)} />
      <button
        type="button"
        className="absolute inset-y-0 right-3 flex items-center text-app-muted hover:text-app"
        onClick={() => setVisible((v) => !v)}
        aria-label={visible ? 'Ocultar contraseña' : 'Mostrar contraseña'}
        title={visible ? 'Ocultar contraseña' : 'Mostrar contraseña'}
      >
        {visible ? <EyeOff size={18} /> : <Eye size={18} />}
      </button>
    </span>
  )
}
