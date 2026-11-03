from django.db import migrations


class Migration(migrations.Migration):
    """employee -> personal. Only renames the column, no data is touched."""

    dependencies = [
        ('questions', '0010_review_fields'),
    ]

    operations = [
        migrations.RenameField(model_name='question', old_name='employee', new_name='personal'),
    ]
