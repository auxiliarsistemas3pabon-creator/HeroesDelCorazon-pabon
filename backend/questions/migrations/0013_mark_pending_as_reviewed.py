from django.db import migrations
from django.db.models import F


def mark_reviewed(apps, schema_editor):
    # Evaluations now count as soon as they are sent: the ones still waiting for review count too.
    Question = apps.get_model("questions", "Question")
    Question.objects.filter(reviewed_at__isnull=True).update(reviewed_at=F("created_at"))


class Migration(migrations.Migration):
    dependencies = [("questions", "0012_personal_labels")]

    operations = [migrations.RunPython(mark_reviewed, migrations.RunPython.noop)]
