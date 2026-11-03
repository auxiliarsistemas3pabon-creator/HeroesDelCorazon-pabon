from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("questions", "0030_evaluation_areas")]

    operations = [
        migrations.AddField(
            model_name="evaluation",
            name="personal_ids",
            field=models.JSONField(blank=True, default=list, verbose_name="Staff to evaluate"),
        ),
    ]
