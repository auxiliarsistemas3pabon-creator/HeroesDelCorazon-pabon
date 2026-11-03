from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0002_role_values_to_english'),
    ]

    operations = [
        migrations.RenameField(model_name='user', old_name='rol', new_name='role'),
        migrations.AddField(
            model_name='user',
            name='area',
            field=models.CharField(blank=True, default='', max_length=100, verbose_name='Area'),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='user',
            name='role',
            field=models.CharField(choices=[('boss', 'Area boss'), ('collaborator', 'Collaborator')], default='collaborator', max_length=20, verbose_name='Role'),
        ),
    ]
