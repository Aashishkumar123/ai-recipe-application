from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ai_recipe_app", "0005_step_detail_cache"),
    ]

    operations = [
        migrations.AddField(
            model_name="chat",
            name="is_pinned",
            field=models.BooleanField(default=False),
        ),
    ]
