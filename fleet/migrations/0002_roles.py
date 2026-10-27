"""Default roles. Assign users to a group in Admin › Users."""

from django.contrib.auth.management import create_permissions
from django.db import migrations

MANAGER = 'Fleet Manager'
VIEWER = 'Fleet Viewer'


def create_roles(apps, schema_editor):
    for app_config in apps.get_app_configs():
        app_config.models_module = True
        create_permissions(app_config, verbosity=0)
        app_config.models_module = None
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')
    fleet_perms = Permission.objects.filter(content_type__app_label='fleet')
    manager, _ = Group.objects.get_or_create(name=MANAGER)
    manager.permissions.set(fleet_perms)
    viewer, _ = Group.objects.get_or_create(name=VIEWER)
    # Viewers see the fleet but not stored documents (which may contain personal data).
    viewer.permissions.set(fleet_perms.filter(codename__startswith='view_').exclude(codename='view_document'))


def remove_roles(apps, schema_editor):
    apps.get_model('auth', 'Group').objects.filter(name__in=[MANAGER, VIEWER]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('fleet', '0001_initial'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [migrations.RunPython(create_roles, remove_roles)]
