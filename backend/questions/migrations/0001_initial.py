import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    """Original schema (Spanish columns). Later migrations move it to the English one."""

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Question',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('area', models.CharField(max_length=100)),
                ('categoria', models.CharField(max_length=50)),
                ('criterio', models.CharField(max_length=200)),
                ('puntuacion', models.PositiveSmallIntegerField(validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)])),
                ('fecha', models.DateTimeField(auto_now_add=True)),
                ('colaborador', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='evaluaciones_realizadas', to=settings.AUTH_USER_MODEL)),
                ('empleado', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='evaluaciones_recibidas', to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
