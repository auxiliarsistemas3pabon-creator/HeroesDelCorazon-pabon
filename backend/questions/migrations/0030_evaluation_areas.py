from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("questions", "0029_evaluation_closes_on_optional")]

    operations = [
        migrations.AddField(
            model_name="evaluation",
            name="areas",
            field=models.JSONField(blank=True, default=list, verbose_name="Areas to evaluate"),
        ),
    ]
