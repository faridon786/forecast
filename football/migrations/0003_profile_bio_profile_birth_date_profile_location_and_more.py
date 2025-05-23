# Generated by Django 5.2.1 on 2025-05-21 10:40

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('football', '0002_alter_match_options_match_sport'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='bio',
            field=models.TextField(blank=True, max_length=500, verbose_name='درباره من'),
        ),
        migrations.AddField(
            model_name='profile',
            name='birth_date',
            field=models.DateField(blank=True, null=True, verbose_name='تاریخ تولد'),
        ),
        migrations.AddField(
            model_name='profile',
            name='location',
            field=models.CharField(blank=True, max_length=100, verbose_name='موقعیت'),
        ),
        migrations.DeleteModel(
            name='UserProfile',
        ),
    ]
