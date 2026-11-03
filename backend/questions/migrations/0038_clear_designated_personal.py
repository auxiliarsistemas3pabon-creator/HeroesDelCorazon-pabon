from django.db import migrations


def clear_personal_ids(apps, schema_editor):
    """The boss no longer designates people: collaborators choose them (manual) or the system assigns them (random)."""
    Evaluation = apps.get_model("questions", "Evaluation")
    Evaluation.objects.exclude(personal_ids=[]).update(personal_ids=[])


class Migration(migrations.Migration):

    dependencies = [
        ("questions", "0037_evaluation_random_selection"),
    ]

    operations = [
        migrations.RunPython(clear_personal_ids, migrations.RunPython.noop),
    ]
