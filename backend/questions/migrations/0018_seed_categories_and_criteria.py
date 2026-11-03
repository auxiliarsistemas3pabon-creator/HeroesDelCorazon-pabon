from django.db import migrations

# The form that used to be written in the code: 4 categories with 3 questions each.
FORM = [
    ("capacidad_de_respuesta", "Capacidad de respuesta", [
        ("META", "Demuestra cumplimiento de metas, objetivos y funciones en el área asignada en los tiempos establecidos."),
        ("EFECTIVA", "Mantiene respuestas oportunas en la labor asignada, y gestiona los recursos personales e institucionales para generar una respuesta efectiva."),
        ("PRODUCTIVIDAD", "Demuestra productividad y efectividad en la relación tiempo-tarea, en los diferentes contextos institucionales."),
    ]),
    ("apropiacion_del_rol", "Apropiación del rol", [
        ("IMPLEMENTA", "Implementa y comparte sus habilidades y conocimientos con el equipo de trabajo."),
        ("APRENDIZAJE", "Demuestra aprendizaje continuo y capacidad de respuesta al cambio."),
        ("RECEPTIVA", "Mantiene una actitud receptiva y de compromiso ante las diversas situaciones promoviendo el trabajo articulado."),
    ]),
    ("comunicacion", "Comunicación", [
        ("RESPETA", "Respeta el conducto regular acatando las directrices y desarrolla una comunicación clara y precisa con los grupos de interés."),
        ("ESCUCHA", "Maneja una escucha activa, con respuestas asertivas a diferentes grupos de interés."),
        ("FOMENTA", "Fomenta un ambiente laboral positivo desde el fortalecimiento de las relaciones interpersonales."),
    ]),
    ("compromiso_organizacional", "Compromiso organizacional", [
        ("INTERACCION", "Genera interacción y respuesta asertiva en el equipo de trabajo y con otras áreas manteniendo la imagen de la institución."),
        ("CONOCIMIENTO", "Demuestra conocimiento, adherencia y cumplimiento a las políticas institucionales."),
        ("DISPOSICION", "Demuestra disposición e interés en cooperar y dar respuesta oportuna a necesidades del área y/o institucionales."),
    ]),
]


def seed(apps, schema_editor):
    Category = apps.get_model("questions", "Category")
    Criterion = apps.get_model("questions", "Criterion")
    for position, (code, name, criteria) in enumerate(FORM, start=1):
        category, _ = Category.objects.get_or_create(code=code, defaults={"name": name, "order": position})
        for number, (criterion_code, text) in enumerate(criteria, start=1):
            Criterion.objects.get_or_create(
                code=criterion_code, defaults={"category": category, "name": text, "order": number}
            )


class Migration(migrations.Migration):
    dependencies = [("questions", "0017_dynamic_categories_and_criteria")]

    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
