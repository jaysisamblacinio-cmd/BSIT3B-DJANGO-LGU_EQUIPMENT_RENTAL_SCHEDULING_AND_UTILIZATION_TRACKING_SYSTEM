import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.settings')
import django
django.setup()

from django.contrib.auth.models import Group

groups = ['Admin', 'Equipment Officer', 'Finance Officer', 'Equipment Operator', 'Applicant']
for g in groups:
    group_obj, created = Group.objects.get_or_create(name=g)
    print(f"Group: {group_obj.name} (created: {created})")
