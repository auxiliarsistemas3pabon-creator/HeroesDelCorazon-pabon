from django.db import migrations

NAME = "Evaluación de desempeño"


def group(apps, schema_editor):
    """The categories and scores that existed before evaluations were independent go into one evaluation."""
    Evaluation = apps.get_model("questions", "Evaluation")
    Category = apps.get_model("questions", "Category")
    Question = apps.get_model("questions", "Question")
    evaluation = Evaluation.objects.first() or Evaluation.objects.create(name=NAME, is_open=True)
    Category.objects.filter(evaluation__isnull=True).update(evaluation=evaluation)
    Question.objects.filter(evaluation__isnull=True).update(evaluation=evaluation)


class Migration(migrations.Migration):
    dependencies = [("questions", "0019_evaluation")]

    operations = [migrations.RunPython(group, migrations.RunPython.noop)]
