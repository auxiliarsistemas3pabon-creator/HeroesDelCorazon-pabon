import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("questions", "0027_assign_legacy_evaluations_to_single_boss"),
    ]

    operations = [
        migrations.AlterField(
            model_name="evaluation",
            name="rating_type",
            field=models.CharField(
                choices=[
                    ("quantitative", "Quantitative"),
                    ("quantitative_10", "Quantitative 1 to 10"),
                    ("descriptive", "Descriptive"),
                    ("descriptive_performance", "Performance or compliance"),
                    ("descriptive_service", "Service quality"),
                    ("descriptive_equipment", "Biomedical equipment condition"),
                    ("descriptive_risk", "Clinical or technical risk"),
                    ("descriptive_compliance", "Requirements compliance"),
                ],
                default="quantitative",
                max_length=24,
                verbose_name="Rating type",
            ),
        ),
        migrations.AlterField(
            model_name="question",
            name="score",
            field=models.PositiveSmallIntegerField(
                validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(10)],
                verbose_name="Score",
            ),
        ),
    ]
