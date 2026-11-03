from django.db import migrations

CRITERIA = {
    'GOALS': 'META', 'EFFECTIVE_RESPONSE': 'EFECTIVA', 'PRODUCTIVITY': 'PRODUCTIVIDAD',
    'SHARES_SKILLS': 'IMPLEMENTA', 'CONTINUOUS_LEARNING': 'APRENDIZAJE', 'RECEPTIVE_ATTITUDE': 'RECEPTIVA',
    'CHAIN_OF_COMMAND': 'RESPETA', 'ACTIVE_LISTENING': 'ESCUCHA', 'POSITIVE_CLIMATE': 'FOMENTA',
    'INTERACTION': 'INTERACCION', 'POLICY_COMPLIANCE': 'CONOCIMIENTO', 'AVAILABILITY': 'DISPOSICION',
}
CATEGORIES = {
    'response_capacity': 'capacidad_de_respuesta',
    'role_ownership': 'apropiacion_del_rol',
    'communication': 'comunicacion',
    'organizational_commitment': 'compromiso_organizacional',
}


def _case(column, mapping):
    whens = ' '.join(f"WHEN '{old}' THEN '{new}'" for old, new in mapping.items())
    return f"CASE {column} {whens} ELSE {column} END"


def _reverse(mapping):
    return {new: old for old, new in mapping.items()}


def _sql(criteria, categories):
    return (
        f"UPDATE questions_evaluation SET criterion = {_case('criterion', criteria)}, "
        f"category = {_case('category', categories)};"
    )


class Migration(migrations.Migration):
    """Criteria and categories keep Spanish codes. Only translates values; no row is removed."""

    dependencies = [
        ('questions', '0006_alter_evaluation_options_alter_evaluation_area_and_more'),
    ]

    operations = [
        migrations.RunSQL(sql=_sql(CRITERIA, CATEGORIES), reverse_sql=_sql(_reverse(CRITERIA), _reverse(CATEGORIES))),
    ]
