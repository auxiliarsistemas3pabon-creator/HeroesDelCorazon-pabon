import { Button } from './ui/Button'
import { ALERT_ERROR, ALERT_OK, FIELD, LABEL } from './ui/styles'
import { useEvaluationProgram } from '../lib/useEvaluationProgram'

// Envuelve useEvaluationProgram + EvaluationProgramFields para una evaluación concreta.
// Se usa con `key={evaluation?.id ?? 'none'}` desde quien la llama: al cambiar de evaluación
// este componente se remonta entero, así el hook arranca con el estado de la nueva evaluación
// sin necesitar un efecto que resetee los campos a mano.
export function EvaluationProgramEditor({ evaluation, staff, onSaved, disabled = false, createNew = false }) {
  const program = useEvaluationProgram({ evaluation, staff, onSaved, createNew })
  return <EvaluationProgramFields program={program} disabled={disabled} createNew={createNew} />
}

// Campos de la "programación" de una evaluación (áreas, modo de selección, fecha de cierre y límite
// mensual). `program` viene de useEvaluationProgram. `disabled` deshabilita todo el bloque,
// por ejemplo mientras no se ha elegido ninguna evaluación en el formulario de creación.
export function EvaluationProgramFields({ program, disabled = false, createNew = false }) {
  const {
    availableAreas,
    value, setValue,
    randomSelection, setRandomSelection,
    closeDate, setCloseDate,
    selectedAreas, toggleArea, selectAllAreas,
    scopedStaff, scopedEvaluators, allAreasSelected,
    evaluatorIds, setAllEvaluators, toggleEvaluator, evaluatorsInvalid,
    validLimit, hasChanges,
    loading, busy, error, message,
    submit,
  } = program

  // Se bloquea todo mientras carga el límite mensual o se guarda, para evitar ediciones sobre datos a medias.
  const fieldsDisabled = disabled || loading || busy

  return (
    <form onSubmit={submit} className="grid gap-4">
      <fieldset className="grid gap-2" disabled={fieldsDisabled}>
        <legend className={LABEL}>Área(s) a evaluar</legend>
        <label className="flex items-center gap-2 rounded-lg border border-app px-3 py-2.5 text-sm text-app">
          <input
            className="accent-primary"
            type="checkbox"
            checked={allAreasSelected}
            onChange={selectAllAreas}
          />
          Todas las áreas
        </label>
        <div className="grid gap-2 sm:grid-cols-2">
          {availableAreas.map((area) => (
            <label key={area} className="flex items-center gap-2 rounded-lg border border-app px-3 py-2.5 text-sm text-app">
              <input
                className="accent-primary"
                type="checkbox"
                checked={selectedAreas === null || selectedAreas.includes(area)}
                onChange={() => toggleArea(area)}
              />
              {area}
            </label>
          ))}
        </div>
        <p className="text-xs text-app-muted">
          Cada colaborador solo podrá evaluar personas de su propia área. «Todas las áreas» habilita la evaluación en todas.
        </p>
      </fieldset>


      <fieldset className="grid gap-2" disabled={fieldsDisabled}>
        <legend className={LABEL}>Usuarios que van a evaluar</legend>
        <label className="flex items-center gap-2 rounded-lg border border-app px-3 py-2.5 text-sm text-app">
          <input
            className="accent-primary"
            type="checkbox"
            checked={evaluatorIds === null}
            onChange={(event) => setAllEvaluators(event.target.checked)}
          />
          Todos los colaboradores de las áreas seleccionadas
        </label>
        {scopedEvaluators.length === 0 && <p className="text-sm text-app-muted">No hay colaboradores en las áreas seleccionadas.</p>}
        <div className="grid max-h-64 gap-2 overflow-y-auto sm:grid-cols-2">
          {scopedEvaluators.map((person) => (
            <label key={person.id} className="flex items-center gap-2 rounded-lg border border-app px-3 py-2.5 text-sm text-app">
              <input
                className="accent-primary"
                type="checkbox"
                checked={evaluatorIds === null || evaluatorIds.includes(person.id)}
                onChange={() => toggleEvaluator(person.id)}
              />
              <span>{person.first_name} {person.last_name}</span>
              <span className="ml-auto text-xs text-app-muted">{person.area}</span>
            </label>
          ))}
        </div>
        <p className="text-xs text-app-muted">
          {evaluatorsInvalid
            ? 'Selecciona al menos un colaborador.'
            : `${evaluatorIds === null ? scopedEvaluators.length : evaluatorIds.length} colaborador(es) evaluarán. No cambia la selección manual o aleatoria de los usuarios a evaluar.`}
        </p>
      </fieldset>

      <label className={`${LABEL} w-full max-w-xs`}>
        Fecha de cierre
        <input
          className={FIELD}
          type="date"
          value={closeDate}
          disabled={fieldsDisabled}
          onChange={(event) => setCloseDate(event.target.value)}
          required
        />
        <span className="text-xs font-normal text-app-muted">La evaluación se cerrará al finalizar ese día.</span>
      </label>

      <fieldset className="grid gap-2" disabled={fieldsDisabled}>
        <legend className={LABEL}>Selección de usuarios</legend>
        <label className="flex items-center gap-2 rounded-lg border border-app px-3 py-2.5 text-sm text-app">
          <input
            className="accent-primary"
            type="checkbox"
            checked={!randomSelection}
            onChange={() => setRandomSelection(false)}
          />
          Selección manual
        </label>
        <label className="flex items-center gap-2 rounded-lg border border-app px-3 py-2.5 text-sm text-app">
          <input
            className="accent-primary"
            type="checkbox"
            checked={randomSelection}
            onChange={() => setRandomSelection(true)}
          />
          Selección aleatoria
        </label>
        <p className="text-xs text-app-muted">
          {randomSelection
            ? `El sistema asigna automáticamente a cada colaborador las personas que va a evaluar, de su misma área (${scopedStaff.length} disponibles).`
            : `Cada colaborador elige a quién evaluar entre las personas de su misma área (${scopedStaff.length} disponibles).`}
        </p>
      </fieldset>

      <label className={`${LABEL} w-full max-w-xs`}>
        Usuarios
        <input
          className={FIELD}
          type="number"
          min="1"
          max="30"
          step="1"
          value={value}
          placeholder={disabled ? 'Selecciona una evaluación primero' : ''}
          onChange={(e) => randomSelection && setValue(e.target.value)}
          onKeyDown={(e) => ['-', '+', '.', 'e', 'E'].includes(e.key) && e.preventDefault()}
          required
        />
        <span className="text-xs font-normal text-app-muted">
          {randomSelection
            ? 'Cantidad fija de usuarios que el sistema asigna a cada colaborador; no se puede modificar.'
            : 'Cantidad de usuarios que cada colaborador debe evaluar.'}
        </span>
      </label>

      <div className="flex justify-end">
        <Button type="submit" disabled={fieldsDisabled || !validLimit || evaluatorsInvalid || !hasChanges}>
          {busy ? 'Guardando...' : createNew ? 'Crear evaluación programada' : 'Guardar programación'}
        </Button>
      </div>

      {error && <div role="alert" className={ALERT_ERROR}>{error}</div>}
      {message && <div className={ALERT_OK}>{message}</div>}
      {loading && <p className="text-sm text-app-muted">Cargando programación...</p>}
    </form>
  )
}
