import calendar

from django.db import migrations, models
from django.utils import timezone


def close_at_month_end(apps, schema_editor):
    """The evaluations that existed have no deadline yet: they close at the end of the current month."""
    Evaluation = apps.get_model("questions", "Evaluation")
    today = timezone.localdate()
    last_day = today.replace(day=calendar.monthrange(today.year, today.month)[1])
    Evaluation.objects.filter(closes_on__isnull=True).update(closes_on=last_day)


class Migration(migrations.Migration):
    dependencies = [("questions", "0021_evaluation_required")]

    operations = [
        migrations.AddField(
            model_name="evaluation",
            name="closes_on",
            field=models.DateField(blank=True, null=True, verbose_name="Closing date"),
        ),
        migrations.RunPython(close_at_month_end, migrations.RunPython.noop),
    ]
