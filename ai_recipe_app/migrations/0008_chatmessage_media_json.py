from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ai_recipe_app', '0007_chatmessage_raw_content'),
    ]

    operations = [
        migrations.AddField(
            model_name='chatmessage',
            name='media_json',
            field=models.TextField(blank=True, default='{}'),
        ),
    ]
