# -*- coding: utf-8 -*-
# Generated by Django 1.10.2 on 2016-10-18 23:44
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('query', '0001_initial'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='photo',
            options={'ordering': ['status', 'photo_id']},
        ),
    ]
