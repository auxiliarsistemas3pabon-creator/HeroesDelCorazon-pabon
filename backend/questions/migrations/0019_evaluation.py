import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("questions", "0018_seed_categories_and_criteria")]

    operations = [
        migrations.CreateModel(
            name="Evaluation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=150, verbose_name="Name")),
                ("is_open", models.BooleanField(default=True, verbose_name="Open")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Created")),
            ],
            options={"verbose_name": "Evaluation", "verbose_name_plural": "Evaluations", "ordering": ["id"]},
        ),
        migrations.AddField(
            model_name="category",
            name="evaluation",
            field=models.ForeignKey(
                null=True, on_delete=django.db.models.deletion.PROTECT, related_name="categories", to="questions.evaluation"
            ),
        ),
        migrations.AddField(
            model_name="question",
            name="evaluation",
            field=models.ForeignKey(
                null=True, on_delete=django.db.models.deletion.PROTECT, related_name="questions", to="questions.evaluation"
            ),
        ),
    ]
