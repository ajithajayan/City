# Generated by Django 5.1 on 2024-09-18 04:19

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('restaurant_app', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='DeliveryDriver',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_active', models.BooleanField(default=False)),
                ('is_available', models.BooleanField(default=False)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='driver_profile', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ('-is_active',),
            },
        ),
        migrations.CreateModel(
            name='DeliveryOrder',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('accepted', 'Accepted'), ('in_progress', 'In Progress'), ('delivered', 'Delivered'), ('cancelled', 'Cancelled')], default='pending', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('driver', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='orders', to='delivery_drivers.deliverydriver')),
                ('order', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='delivery_order', to='restaurant_app.order')),
            ],
            options={
                'ordering': ('-updated_at',),
            },
        ),
    ]
