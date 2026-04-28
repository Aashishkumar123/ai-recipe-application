from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0003_alter_user_profile_picture'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='dietary_restrictions',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name='user',
            name='cuisine_preferences',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name='user',
            name='cooking_skill',
            field=models.CharField(
                choices=[('beginner', 'Beginner'), ('intermediate', 'Intermediate'), ('advanced', 'Advanced')],
                default='intermediate',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='user',
            name='default_servings',
            field=models.PositiveSmallIntegerField(default=2),
        ),
    ]
