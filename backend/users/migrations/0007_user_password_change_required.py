from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0006_user_position"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="password_change_required",
            field=models.BooleanField(default=False),
        ),
    ]
