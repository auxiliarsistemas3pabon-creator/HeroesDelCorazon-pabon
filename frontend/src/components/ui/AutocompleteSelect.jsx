import { useEffect, useId, useMemo, useRef, useState } from 'react'
import { ChevronDown } from 'lucide-react'
import { FIELD } from './styles'

// Compara sin tildes ni mayúsculas ("Ángel" coincide con "angel").
function normalize(value) {
  return value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase()
}

// Combobox con filtro. `options` = [{ value, label, key? }]; `key` desempata si dos opciones comparten value+label.
// Con `allowCustom` el texto escrito se propaga como valor en cada tecla (permite valores fuera de la lista).
// Teclado: flechas navegan, Enter elige, Escape cierra.
export function AutocompleteSelect({ options, value, onChange, placeholder, allowCustom = false }) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [activeIndex, setActiveIndex] = useState(0)
  const wrapperRef = useRef(null)
  const inputId = useId()
  const listId = useId()
  // Con el desplegable abierto el input muestra lo que se escribe; cerrado, la etiqueta de la opción elegida.
  const selected = options.find((option) => option.value === value)
  const filtered = useMemo(() => {
    const search = normalize(query.trim())
    return search
      ? options.filter((option) => normalize(option.label).includes(search))
      : options
  }, [options, query])

  // Cierra al hacer clic fuera; el listener solo existe mientras está abierto.
  useEffect(() => {
    if (!open) return
    function closeOnOutsideClick(event) {
      if (!wrapperRef.current?.contains(event.target)) {
        setOpen(false)
        setQuery('')
      }
    }
    document.addEventListener('mousedown', closeOnOutsideClick)
    return () => document.removeEventListener('mousedown', closeOnOutsideClick)
  }, [open])

  function openOptions() {
    setQuery('')
    setActiveIndex(0)
    setOpen(true)
  }

  function choose(option) {
    onChange(option.value)
    setQuery('')
    setOpen(false)
  }

  function handleChange(event) {
    const nextQuery = event.target.value
    setQuery(nextQuery)
    setActiveIndex(0)
    setOpen(true)
    if (allowCustom) onChange(nextQuery)
  }

  function handleKeyDown(event) {
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      if (!open) {
        openOptions()
        return
      }
      setActiveIndex((index) => Math.min(index + 1, filtered.length - 1))
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      setActiveIndex((index) => Math.max(index - 1, 0))
    } else if (event.key === 'Enter' && open && filtered[activeIndex]) {
      event.preventDefault()
      choose(filtered[activeIndex])
    } else if (event.key === 'Escape') {
      setOpen(false)
      setQuery('')
    }
  }

  return (
    <div className="relative" ref={wrapperRef}>
      {/* Cerrado y con opción elegida: un <input> no parte el texto en varias líneas, así que se muestra la etiqueta
          en un botón que sí lo hace; al abrir (clic/foco) se cambia por el input con el foco. */}
      {!open && !allowCustom && selected ? (
        <button
          type="button"
          id={inputId}
          role="combobox"
          aria-expanded={false}
          aria-controls={listId}
          className={`${FIELD} pr-10 text-left break-words`}
          onClick={openOptions}
          onFocus={openOptions}
        >
          {selected.label}
        </button>
      ) : (
      <input
        id={inputId}
        autoFocus={open}
        className={`${FIELD} pr-10`}
        type="text"
        role="combobox"
        aria-autocomplete="list"
        aria-expanded={open}
        aria-controls={listId}
        aria-activedescendant={open && filtered[activeIndex] ? `${listId}-option-${activeIndex}` : undefined}
        placeholder={placeholder}
        value={open ? query : selected?.label ?? (allowCustom ? value : '')}
        onFocus={() => { if (!open) openOptions() }}
        onClick={() => { if (!open) openOptions() }}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
      />
      )}
      <span className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-3 text-app-muted" aria-hidden="true">
        <ChevronDown size={16} />
      </span>
      {open && (
        <ul
          id={listId}
          role="listbox"
          className="absolute left-0 right-0 top-full z-20 mt-1 max-h-64 overflow-y-auto rounded-lg border border-app bg-surface shadow-lg"
        >
          {filtered.length === 0 ? (
            <li className="p-3 text-center text-xs text-app-muted">Sin coincidencias.</li>
          ) : filtered.map((option, index) => (
            <li key={option.key ?? `${option.value}:${option.label}`} role="presentation">
              <button
                type="button"
                id={`${listId}-option-${index}`}
                role="option"
                aria-selected={option.value === value}
                className={`flex w-full items-center px-3 py-2.5 text-left text-sm ${
                  index === activeIndex ? 'bg-primary/10 text-primary' : 'text-app hover:bg-app-muted'
                }`}
                onMouseEnter={() => setActiveIndex(index)}
                onClick={() => choose(option)}
              >
                {option.label}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
