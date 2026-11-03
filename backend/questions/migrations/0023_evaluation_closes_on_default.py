from django.db import migrations, models

import questions.models


class Migration(migrations.Migration):
    dependencies = [("questions", "0022_evaluation_closes_on")]

    operations = [
        migrations.AlterField(
            model_name="evaluation",
            name="closes_on",
            field=models.DateField(
                blank=True, default=questions.models.end_of_month, null=True, verbose_name="Closing date"
            ),
        ),
    ]
