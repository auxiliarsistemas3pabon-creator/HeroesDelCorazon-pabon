import { useEffect, useState } from 'react'
import { api, errorMessage } from './api'

const EVALUATIONS = '/questions/evaluations/'
const SETTINGS = '/questions/settings/'
// Área técnica heredada que no debe ofrecerse como destinatario.
const REMOVED_AREA = 'sistema'
// Con selección aleatoria el sistema asigna siempre esta cantidad de personas a cada colaborador (no editable).
const RANDOM_COUNT = 3

function isRemovedArea(area) {
  return area.trim().toLocaleLowerCase() === REMOVED_AREA
}

// Estado y lógica de la "programación" de una evaluación (áreas, modo de selección, cantidad de usuarios y fecha
// de cierre). El jefe NO designa personas: define si cada colaborador elige a quién evaluar (manual) o si el sistema
// se lo asigna (aleatoria). FormProgramPage crea una copia independiente; EvaluationsListPage edita una existente.
export function useEvaluationProgram({ evaluation, staff, onSaved, createNew = false }) {
  const evaluationId = evaluation?.id ?? null
  // `selectedAreas === null` significa "todas las áreas" (se envía null al backend); un array vacío, ninguna.
  const availableAreas = [...new Set(staff.map((person) => person.area).filter((area) => area && !isRemovedArea(area)))].sort()

  // El estado parte directamente de `evaluation`; quien usa el hook lo remonta con `key={evaluationId}` al cambiar de evaluación.
  const [value, setValue] = useState(createNew ? String(RANDOM_COUNT) : '')
  const [saved, setSaved] = useState(null)
  const [selectedAreas, setSelectedAreas] = useState(() => createNew ? null : evaluation ? evaluation.areas : null)
  const [savedAreas, setSavedAreas] = useState(() => createNew ? undefined : evaluation ? evaluation.areas : undefined)
  const [randomSelection, setRandomSelectionState] = useState(() => !createNew && Boolean(evaluation?.random_selection))
  const [savedRandom, setSavedRandom] = useState(() => createNew ? null : Boolean(evaluation?.random_selection))
  const [closeDate, setCloseDate] = useState(() => createNew ? '' : evaluation?.closes_on ?? '')
  const [savedCloseDate, setSavedCloseDate] = useState(() => createNew ? null : evaluation ? evaluation.closes_on ?? '' : null)
  // Colaboradores que evaluarán. `evaluatorIds === null` significa todos los de las áreas (se envía [] al backend).
  // Es independiente de la selección manual/aleatoria de los usuarios a evaluar.
  const [evaluators, setEvaluators] = useState([])
  const [evaluatorIds, setEvaluatorIds] = useState(() => createNew || !evaluation?.evaluator_ids?.length ? null : evaluation.evaluator_ids)
  const [savedEvaluatorIds, setSavedEvaluatorIds] = useState(() => createNew ? undefined : evaluation ? evaluation.evaluator_ids ?? [] : undefined)
  const [message, setMessage] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  // El límite mensual todavía no llegó mientras `saved` sigue en null y no hubo error.
  const loading = !createNew && evaluationId != null && saved === null && error === null

  useEffect(() => {
    let current = true
    api('/users/evaluators/')
      .then((list) => current && setEvaluators(list))
      .catch(() => {})
    return () => { current = false }
  }, [])

  // Trae el límite mensual vigente de la evaluación (se guarda aparte, no viene en `evaluation`).
  useEffect(() => {
    if (!evaluationId || createNew) return
    let current = true
    api(`${SETTINGS}?evaluation=${evaluationId}`)
      .then((data) => {
        if (!current) return
        setValue(String(data.monthly_limit))
        setSaved(data.monthly_limit)
      })
      .catch((e) => current && setError(errorMessage(e)))
    return () => { current = false }
  }, [createNew, evaluationId])

  // Límite mensual: entero entre 1 y 30 (mismo rango que valida el backend).
  const validLimit = /^[0-9]+$/.test(value) && Number(value) >= 1 && Number(value) <= 30
  // Los *Changed comparan contra lo último guardado; sirven para enviar solo lo modificado y activar el botón Guardar.
  const limitChanged = saved !== null && Number(value) !== saved
  const closeDateChanged = savedCloseDate !== null && closeDate !== savedCloseDate
  const randomChanged = savedRandom !== null && randomSelection !== savedRandom
  const areasChanged = savedAreas !== undefined && (
    selectedAreas === null || savedAreas === null
      ? selectedAreas !== savedAreas
      : [...selectedAreas].sort().join('\0') !== [...savedAreas].sort().join('\0')
  )
  const allAreasSelected = selectedAreas === null
    || (availableAreas.length > 0 && selectedAreas.length === availableAreas.length)
  const scopedStaff = staff.filter((person) => selectedAreas === null || selectedAreas.includes(person.area))
  const scopedEvaluators = evaluators.filter((person) => selectedAreas === null || selectedAreas.includes(person.area))
  const evaluatorsInvalid = evaluatorIds !== null && evaluatorIds.length === 0
  // Lo que se envía: [] = todos los colaboradores de las áreas.
  const evaluatorsPayload = evaluatorIds ?? []
  const evaluatorsChanged = savedEvaluatorIds !== undefined
    && [...evaluatorsPayload].sort((a, b) => a - b).join(',') !== [...savedEvaluatorIds].sort((a, b) => a - b).join(',')
  const hasChanges = createNew || limitChanged || closeDateChanged || areasChanged || randomChanged || evaluatorsChanged

  // Al cambiar las áreas se descartan los colaboradores marcados que ya no pertenecen a ellas.
  function changeAreas(nextAreas) {
    setSelectedAreas(nextAreas)
    if (nextAreas !== null) setEvaluatorIds((current) => current === null ? null : current.filter((id) => {
      const person = evaluators.find((item) => item.id === id)
      return person && nextAreas.includes(person.area)
    }))
  }

  function toggleArea(area) {
    const currentAreas = selectedAreas ?? availableAreas
    changeAreas(currentAreas.includes(area) ? currentAreas.filter((item) => item !== area) : [...currentAreas, area])
  }

  function selectAllAreas() {
    changeAreas(allAreasSelected ? [] : null)
  }

  function setAllEvaluators(all) {
    setEvaluatorIds(all ? null : [])
  }

  // Primer clic con «todos» activo: pasa a selección específica partiendo de todos menos ese.
  function toggleEvaluator(personId) {
    setEvaluatorIds((current) => {
      if (current === null) return scopedEvaluators.map((person) => person.id).filter((id) => id !== personId)
      return current.includes(personId) ? current.filter((id) => id !== personId) : [...current, personId]
    })
  }

  // Manual y aleatoria son excluyentes. Aleatoria fija la cantidad en RANDOM_COUNT; manual la deja editable.
  function setRandomSelection(enabled) {
    setRandomSelectionState(enabled)
    if (enabled) setValue(String(RANDOM_COUNT))
  }

  // Crear: POST a /programs/ (copia nueva de la evaluación). Editar: PATCH de fecha/áreas/modo y PUT aparte
  // del límite mensual (vive en otro recurso), cada uno solo si cambió.
  async function submit(event) {
    event?.preventDefault?.()
    if (!evaluationId || !validLimit) {
      setError('Ingresa un número entero de usuarios entre 1 y 30.')
      return
    }
    if (!closeDate) {
      setError('Selecciona la fecha de cierre.')
      return
    }
    if (evaluatorsInvalid) {
      setError('Selecciona al menos un usuario que va a evaluar o marca todos.')
      return
    }
    if (!hasChanges) return
    setError(null)
    setMessage(null)
    setBusy(true)
    try {
      if (createNew) {
        const created = await api(`${EVALUATIONS}${evaluationId}/programs/`, {
          method: 'POST',
          body: {
            closes_on: closeDate,
            areas: selectedAreas,
            personal_ids: [],
            evaluator_ids: evaluatorsPayload,
            monthly_limit: Number(value),
            random_selection: randomSelection,
          },
        })
        setMessage(`Nueva evaluación programada: «${created.name}».`)
        onSaved?.(created)
        return
      }

      let updated = evaluation
      if (closeDateChanged || areasChanged || randomChanged || evaluatorsChanged) {
        updated = await api(`${EVALUATIONS}${evaluationId}/`, {
          method: 'PATCH',
          body: { closes_on: closeDate, areas: selectedAreas, random_selection: randomSelection, evaluator_ids: evaluatorsPayload },
        })
        setSavedCloseDate(closeDate)
        setSavedAreas(selectedAreas)
        setSavedRandom(randomSelection)
        setSavedEvaluatorIds(evaluatorsPayload)
      }
      if (limitChanged) {
        await api(SETTINGS, {
          method: 'PUT',
          body: { evaluation: Number(evaluationId), monthly_limit: Number(value) },
        })
        setSaved(Number(value))
      }
      setMessage(`Programación guardada para «${evaluation.name}».`)
      onSaved?.(updated)
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  return {
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
  }
}
