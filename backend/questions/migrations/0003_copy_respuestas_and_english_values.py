from django.db import migrations

# Old Spanish criterion codes -> new English codes (INTERCCION was a typo of INTERACCION).
CRITERIA = {
    'META': 'GOALS',
    'EFECTIVA': 'EFFECTIVE_RESPONSE',
    'PRODUCTIVIDAD': 'PRODUCTIVITY',
    'IMPLEMENTA': 'SHARES_SKILLS',
    'APRENDIZAJE': 'CONTINUOUS_LEARNING',
    'RECEPTIVA': 'RECEPTIVE_ATTITUDE',
    'RESPETA': 'CHAIN_OF_COMMAND',
    'ANALISIS': 'ACTIVE_LISTENING',
    'ESCUCHA': 'ACTIVE_LISTENING',
    'FOMENTA': 'POSITIVE_CLIMATE',
    'INTERCCION': 'INTERACTION',
    'INTERACCION': 'INTERACTION',
    'CONOCIMIENTO': 'POLICY_COMPLIANCE',
    'DISPOSICION': 'AVAILABILITY',
}

CATEGORIES = {
    'capacidad de respuesta': 'response_capacity',
    'apropiación del rol': 'role_ownership',
    'comunicación': 'communication',
    'compromiso organizacional': 'organizational_commitment',
}

# Each category groups 3 criteria (same order as the model).
CATEGORY_OF_CRITERION = {
    'GOALS': 'response_capacity', 'EFFECTIVE_RESPONSE': 'response_capacity', 'PRODUCTIVITY': 'response_capacity',
    'SHARES_SKILLS': 'role_ownership', 'CONTINUOUS_LEARNING': 'role_ownership', 'RECEPTIVE_ATTITUDE': 'role_ownership',
    'CHAIN_OF_COMMAND': 'communication', 'ACTIVE_LISTENING': 'communication', 'POSITIVE_CLIMATE': 'communication',
    'INTERACTION': 'organizational_commitment', 'POLICY_COMPLIANCE': 'organizational_commitment',
    'AVAILABILITY': 'organizational_commitment',
}


def _case(column, mapping, otherwise=None):
    whens = ' '.join(f"WHEN '{old}' THEN '{new}'" for old, new in mapping.items())
    return f"CASE {column} {whens} ELSE {otherwise or column} END"


# 1) Every old Respuesta becomes its own row (nothing is deleted), then 2) values are translated.
SQL = f"""
INSERT INTO questions_question (area, categoria, criterio, puntuacion, fecha, colaborador_id, empleado_id)
SELECT q.area, q.categoria, r.criterio, r.puntuacion, q.fecha, q.colaborador_id, q.empleado_id
FROM questions_respuesta r JOIN questions_question q ON q.id = r.evaluacion_id;

UPDATE questions_question SET criterio = {_case('criterio', CRITERIA)};
UPDATE questions_question SET categoria = {_case('categoria', CATEGORIES)};
UPDATE questions_question SET categoria = {_case('criterio', CATEGORY_OF_CRITERION, otherwise='categoria')};
"""


class Migration(migrations.Migration):

    dependencies = [
        ('questions', '0002_respuesta'),
    ]

    operations = [
        migrations.RunSQL(sql=SQL, reverse_sql=migrations.RunSQL.noop),
    ]
