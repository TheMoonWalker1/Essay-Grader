# Generated by Django 3.0.6 on 2020-06-02 01:39

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('grader_app', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='teachers',
            field=models.TextField(default='{"period_1_teacher": "", "period_2_teacher": "", "period_3_teacher": "", "period_4_teacher": "", "period_5_teacher": "", "period_6_teacher": "", "period_7_teacher": ""}'),
        ),
    ]