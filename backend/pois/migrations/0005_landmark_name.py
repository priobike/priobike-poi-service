# Generated by Django 4.2.13 on 2024-07-12 09:27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pois', '0004_landmark_tags_alter_landmark_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='landmark',
            name='name',
            field=models.TextField(default=''),
            preserve_default=False,
        ),
    ]
