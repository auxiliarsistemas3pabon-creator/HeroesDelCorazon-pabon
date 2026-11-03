from django.db import migrations


class Migration(migrations.Migration):
    """Its rows were already copied into Evaluation by migration 0003."""

    dependencies = [
        ('questions', '0004_rename_to_english'),
    ]

    operations = [
        migrations.DeleteModel(name='Respuesta'),
    ]
