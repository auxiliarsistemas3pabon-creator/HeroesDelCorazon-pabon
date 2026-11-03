from django.db import migrations, models


class Migration(migrations.Migration):
    """Spanish -> English names. Only renames, so no data is touched."""

    dependencies = [
        ('questions', '0003_copy_respuestas_and_english_values'),
    ]

    operations = [
        migrations.RenameModel(old_name='Question', new_name='Evaluation'),
        migrations.RenameField(model_name='evaluation', old_name='colaborador', new_name='evaluator'),
        migrations.RenameField(model_name='evaluation', old_name='empleado', new_name='employee'),
        migrations.RenameField(model_name='evaluation', old_name='categoria', new_name='category'),
        migrations.RenameField(model_name='evaluation', old_name='criterio', new_name='criterion'),
        migrations.RenameField(model_name='evaluation', old_name='puntuacion', new_name='score'),
        migrations.RenameField(model_name='evaluation', old_name='fecha', new_name='created_at'),
        migrations.AlterField(
            model_name='evaluation',
            name='criterion',
            field=models.CharField(max_length=50),
        ),
    ]
