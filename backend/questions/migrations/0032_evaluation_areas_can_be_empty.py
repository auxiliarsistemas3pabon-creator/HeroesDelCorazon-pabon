from django.db import migrations, models


def preserve_existing_all_areas(apps, schema_editor):
    Evaluation = apps.get_model("questions", "Evaluation")
    Evaluation.objects.filter(areas=[]).update(areas=None)


def restore_empty_area_lists(apps, schema_editor):
    Evaluation = apps.get_model("questions", "Evaluation")
    Evaluation.objects.filter(areas__isnull=True).update(areas=[])


class Migration(migrations.Migration):
    dependencies = [("questions", "0031_evaluation_personal_ids")]

    operations = [
        migrations.AlterField(
            model_name="evaluation",
            name="areas",
            field=models.JSONField(
                blank=True,
                default=None,
                null=True,
                verbose_name="Areas to evaluate",
            ),
        ),
        migrations.RunPython(preserve_existing_all_areas, restore_empty_area_lists),
    ]
