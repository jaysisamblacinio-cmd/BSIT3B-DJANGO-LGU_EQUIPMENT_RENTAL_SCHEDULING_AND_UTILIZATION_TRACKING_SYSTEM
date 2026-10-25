import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.settings')
import django
django.setup()

from django.contrib.auth.models import User, Group

groups = ['Admin', 'Equipment Officer', 'Finance Officer', 'Equipment Operator', 'Applicant']
for g in groups:
    group_obj, created = Group.objects.get_or_create(name=g)
    print(f"Group: {group_obj.name} (created: {created})")

role_map = {
    'glenn': 'Admin',
    'officer': 'Equipment Officer',
    'finance': 'Finance Officer',
    'danilo_operator': 'Equipment Operator',
    'farmer_juan': 'Applicant',
    'contractor_mateo': 'Applicant',
}

for uname, rname in role_map.items():
    try:
        u = User.objects.get(username=uname)
        g = Group.objects.get(name=rname)
        u.groups.clear()
        u.groups.add(g)
        u.set_password('password123')
        u.save()
        print(f"Configured {uname} -> {rname}")
    except User.DoesNotExist:
        print(f"User {uname} not found")
