# Il registro delle chiamate ora lo tiene cornhub (ADR 0021).

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ai', '0002_aicall_service_tier'),
    ]

    operations = [
        migrations.DeleteModel(
            name='AiCall',
        ),
    ]
