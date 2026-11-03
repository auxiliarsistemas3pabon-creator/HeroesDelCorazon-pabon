// Escalas de calificación disponibles al crear una evaluación. La clave es el `rating_type` que guarda el backend
// (deben coincidir). `score` es el valor numérico almacenado; `label` es lo que ve el usuario; `max` es la nota máxima
// de la escala. Ojo: en descriptive_compliance 'No aplica' vale 0 y se excluye del promedio (ver ScoreTable: n > 0).
export const RATING_SCALES = {
  quantitative: {
    label: 'Cuantitativa: de 1 a 5',
    description: 'Escala numérica de 1 a 5.',
    options: [1, 2, 3, 4, 5].map((score) => ({ score, label: String(score) })),
    max: 5,
  },
  quantitative_10: {
    label: 'Cuantitativa: de 1 a 10',
    description: 'Escala numérica de 1 a 10.',
    options: Array.from({ length: 10 }, (_, index) => ({ score: index + 1, label: String(index + 1) })),
    max: 10,
  },
  descriptive: {
    label: 'Cualitativa: Malo a Excelente',
    description: 'Malo, Regular, Bueno, Muy bueno o Excelente.',
    options: ['Malo', 'Regular', 'Bueno', 'Muy bueno', 'Excelente'].map((label, index) => ({ score: index + 1, label })),
    max: 5,
  },
  descriptive_performance: {
    label: 'Escala de desempeño o cumplimiento',
    description: 'Excelente, Bueno, Aceptable, Deficiente o Crítico.',
    options: ['Crítico', 'Deficiente', 'Aceptable', 'Bueno', 'Excelente'].map((label, index) => ({ score: index + 1, label })),
    max: 5,
  },
  descriptive_service: {
    label: 'Escala de calidad del servicio',
    description: 'Mala, Regular, Buena, Muy buena o Excelente.',
    options: ['Mala', 'Regular', 'Buena', 'Muy buena', 'Excelente'].map((label, index) => ({ score: index + 1, label })),
    max: 5,
  },
  descriptive_equipment: {
    label: 'Escala del estado de equipos biomédicos',
    description: 'Fuera de servicio, Deficiente, Aceptable, Bueno o Excelente.',
    options: ['Fuera de servicio', 'Deficiente', 'Aceptable', 'Bueno', 'Excelente'].map((label, index) => ({ score: index + 1, label })),
    max: 5,
  },
  descriptive_risk: {
    label: 'Escala de riesgo clínico o técnico',
    description: 'Muy bajo, Bajo, Moderado, Alto o Crítico.',
    options: ['Muy bajo', 'Bajo', 'Moderado', 'Alto', 'Crítico'].map((label, index) => ({ score: index + 1, label })),
    max: 5,
  },
  descriptive_compliance: {
    label: 'Escala de cumplimiento de requisitos',
    description: 'No cumple, Cumple parcialmente, Cumple totalmente o No aplica.',
    options: [
      { score: 1, label: 'No cumple' },
      { score: 2, label: 'Cumple parcialmente' },
      { score: 3, label: 'Cumple totalmente' },
      { score: 0, label: 'No aplica' },
    ],
    max: 3,
  },
}

// Tipo desconocido o ausente cae en la escala cuantitativa 1-5.
export function ratingScale(type = 'quantitative') {
  return RATING_SCALES[type] ?? RATING_SCALES.quantitative
}

// Etiqueta de una nota; si no existe en la escala devuelve la nota tal cual.
export function ratingLabel(type, score) {
  return ratingScale(type).options.find((option) => option.score === Number(score))?.label ?? score
}
