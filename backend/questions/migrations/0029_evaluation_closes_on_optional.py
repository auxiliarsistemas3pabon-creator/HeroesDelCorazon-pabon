from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("questions", "0028_evaluation_rating_scales_and_score_range")]

    operations = [
        migrations.AlterField(
            model_name="evaluation",
            name="closes_on",
            field=models.DateField(blank=True, null=True, verbose_name="Closing date"),
        ),
    ]
