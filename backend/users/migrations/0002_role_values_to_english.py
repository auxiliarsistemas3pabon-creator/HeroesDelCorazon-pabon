from django.db import migrations


class Migration(migrations.Migration):
    """Keeps the data: jefe -> boss, colaborador -> collaborator."""

    dependencies = [
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                UPDATE users_user SET rol = 'boss' WHERE rol = 'jefe';
                UPDATE users_user SET rol = 'collaborator' WHERE rol = 'colaborador';
            """,
            reverse_sql="""
                UPDATE users_user SET rol = 'jefe' WHERE rol = 'boss';
                UPDATE users_user SET rol = 'colaborador' WHERE rol = 'collaborator';
            """,
        ),
    ]
