from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("questions", "0033_replace_system_area")]

    operations = [
        migrations.AddField(
            model_name="evaluation",
            name="program_started_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Program started"),
        ),
    ]
