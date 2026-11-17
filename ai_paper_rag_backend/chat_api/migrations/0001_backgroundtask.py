from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='BackgroundTask',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('task_id', models.CharField(max_length=64, unique=True)),
                ('task_type', models.CharField(max_length=64)),
                ('status', models.CharField(default='queued', max_length=32)),
                ('progress', models.PositiveIntegerField(default=0)),
                ('message', models.TextField(blank=True, default='')),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('result', models.JSONField(blank=True, null=True)),
                ('error', models.TextField(blank=True, default='')),
                ('created_at', models.FloatField()),
                ('updated_at', models.FloatField()),
            ],
            options={
                'ordering': ['-updated_at', '-id'],
            },
        ),
    ]
