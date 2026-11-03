from django.db import migrations


class Migration(migrations.Migration):
    """Evaluation -> Question and evaluator -> collaborator. Only renames, no data is touched."""

    dependencies = [
        ('questions', '0007_spanish_codes'),
    ]

    operations = [
        migrations.RenameModel(old_name='Evaluation', new_name='Question'),
        migrations.RenameField(model_name='question', old_name='evaluator', new_name='collaborator'),
    ]
