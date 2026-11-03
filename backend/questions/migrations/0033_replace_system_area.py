from django.db import migrations

OLD_AREA = "Sistema"
NEW_AREA = "Sistemas"


def replace_system_area(apps, schema_editor):
    User = apps.get_model("users", "User")
    Evaluation = apps.get_model("questions", "Evaluation")
    Question = apps.get_model("questions", "Question")

    User.objects.filter(area=OLD_AREA).update(area=NEW_AREA)
    Question.objects.filter(area=OLD_AREA).update(area=NEW_AREA)

    for evaluation in Evaluation.objects.exclude(areas__isnull=True).iterator():
        if not isinstance(evaluation.areas, list) or OLD_AREA not in evaluation.areas:
            continue
        evaluation.areas = list(dict.fromkeys(
            NEW_AREA if area == OLD_AREA else area
            for area in evaluation.areas
        ))
        evaluation.save(update_fields=["areas"])


class Migration(migrations.Migration):
    dependencies = [
        ("questions", "0032_evaluation_areas_can_be_empty"),
        ("users", "0007_user_password_change_required"),
    ]

    operations = [
        migrations.RunPython(replace_system_area, migrations.RunPython.noop),
    ]
