# Generated by Django 5.1.1 on 2024-10-11 15:48

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main_app', '0008_alter_dose_content'),
    ]

    operations = [
        migrations.AddField(
            model_name='dose',
            name='author',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
