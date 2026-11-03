import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("questions", "0020_group_existing_into_one_evaluation")]

    operations = [
        migrations.AlterField(
            model_name="category",
            name="evaluation",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, related_name="categories", to="questions.evaluation"
            ),
        ),
        migrations.AlterField(
            model_name="question",
            name="evaluation",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, related_name="questions", to="questions.evaluation"
            ),
        ),
    ]
