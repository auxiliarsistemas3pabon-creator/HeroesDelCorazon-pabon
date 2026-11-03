from django.conf import settings
from django.db import migrations


def assign_to_only_boss(apps, schema_editor):
    User = apps.get_model(*settings.AUTH_USER_MODEL.split("."))
    Evaluation = apps.get_model("questions", "Evaluation")
    bosses = User.objects.filter(role="boss")
    if bosses.count() == 1:
        Evaluation.objects.filter(created_by__isnull=True).update(created_by=bosses.first().pk)


class Migration(migrations.Migration):
    dependencies = [
        ("questions", "0026_evaluation_created_by"),
    ]

    operations = [
        migrations.RunPython(assign_to_only_boss, migrations.RunPython.noop),
    ]
