# Generated by Django 4.2.13 on 2024-07-12 09:12

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pois', '0003_landmark'),
    ]

    operations = [
        migrations.AddField(
            model_name='landmark',
            name='tags',
            field=models.TextField(default='none'),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='landmark',
            name='id',
            field=models.TextField(primary_key=True, serialize=False),
        ),
    ]