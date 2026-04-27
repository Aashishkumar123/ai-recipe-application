from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ai_recipe_app', '0003_alter_chat_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='chat',
            name='is_public',
            field=models.BooleanField(default=False),
        ),
    ]
