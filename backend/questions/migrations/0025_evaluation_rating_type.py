from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("questions", "0024_evaluation_monthly_limit")]

    operations = [
        migrations.AddField(
            model_name="evaluation",
            name="rating_type",
            field=models.CharField(
                choices=[("quantitative", "Quantitative"), ("descriptive", "Descriptive")],
                default="quantitative",
                max_length=20,
                verbose_name="Rating type",
            ),
        ),
    ]
