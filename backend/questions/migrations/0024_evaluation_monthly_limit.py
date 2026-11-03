from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("questions", "0023_evaluation_closes_on_default")]

    operations = [
        migrations.AddField(
            model_name="evaluation",
            name="monthly_limit",
            field=models.PositiveSmallIntegerField(blank=True, default=None, null=True, verbose_name="Monthly limit"),
        ),
    ]
