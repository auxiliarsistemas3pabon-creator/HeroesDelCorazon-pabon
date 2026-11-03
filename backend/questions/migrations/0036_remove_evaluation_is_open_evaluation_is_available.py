from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('questions', '0035_question_updated_at_alter_question_created_at'),
    ]

    operations = [
        # Rename (not remove + add) so evaluations the boss already closed stay closed.
        migrations.RenameField(
            model_name='evaluation',
            old_name='is_open',
            new_name='is_available',
        ),
        migrations.AlterField(
            model_name='evaluation',
            name='is_available',
            field=models.BooleanField(default=True, verbose_name='Available'),
        ),
    ]
