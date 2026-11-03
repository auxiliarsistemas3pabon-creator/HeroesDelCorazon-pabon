import clsx from 'clsx'

// Une clases de Tailwind ignorando las vacías (igual que el software de equipos biomédicos).
export function cn(...inputs) {
  return clsx(inputs)
}
