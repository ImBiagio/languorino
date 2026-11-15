from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0002_user_handle'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='cornhub_sub',
            field=models.UUIDField(blank=True, editable=False, null=True, unique=True),
        ),
    ]
