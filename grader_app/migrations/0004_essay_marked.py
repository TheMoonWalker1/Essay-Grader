# Generated by Django 3.0.7 on 2020-06-09 21:48

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('grader_app', '0003_essay_raw_body'),
    ]

    operations = [
        migrations.AddField(
            model_name='essay',
            name='marked',
            field=models.BooleanField(default=False),
        ),
    ]