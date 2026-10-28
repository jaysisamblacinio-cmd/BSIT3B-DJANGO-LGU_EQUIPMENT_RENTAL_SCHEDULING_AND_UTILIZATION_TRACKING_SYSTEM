import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.settings')
import django
django.setup()

from django.test import Client
from django.contrib.auth.models import User

client = Client()

# 1. Test unauthenticated redirect
resp = client.get('/home/')
assert resp.status_code == 302, f"Expected 302 redirect for unauth home, got {resp.status_code}"
print("Unauthenticated redirect: OK (302)")

# 2. Test login page
resp = client.get('/')
assert resp.status_code == 200, f"Expected 200 for login, got {resp.status_code}"
assert "LGU Equipment Rental System" in resp.content.decode('utf-8', errors='ignore')
print("Login Page: OK (200)")

# 3. Test register page
resp = client.get('/register/')
assert resp.status_code == 200, f"Expected 200 for register, got {resp.status_code}"
print("Register Page: OK (200)")

# 4. Authenticate as an existing administrator account.
admin_user = User.objects.filter(is_superuser=True, is_active=True).first()
assert admin_user is not None, "Create an active superuser before running this verification script."
client.force_login(admin_user)

endpoints = [
    ('/home/', 'Dashboard Overview'),
    ('/rentals/equipment/', 'Equipment Catalog'),
    ('/rentals/equipment/1/', '10-Wheeler Heavy Dump Truck'),
    ('/rentals/apply/', 'Apply for Equipment Rental'),
    ('/rentals/my-requests/', 'My Rental Applications'),
    ('/rentals/requests/', 'Rental Applications'),
    ('/rentals/requests/1/agreement/', 'Government Machinery & Equipment Rental Agreement'),
    ('/rentals/calendar/', 'Equipment Scheduling & Availability Calendar'),
    ('/rentals/calendar/events/', None),  # JSON
    ('/rentals/deployments/', 'Equipment Deployments & Engine Hours'),
    ('/rentals/maintenance/', 'Fleet Maintenance & Repair Records'),
    ('/rentals/payments/', 'Equipment Rental Payments & Treasury Receipts'),
    ('/rentals/payments/1/receipt/', 'Official Collection Receipt'),
    ('/rentals/reports/', 'Executive Reports & Utilization Analytics'),
    ('/rentals/notifications/', 'In-System Notifications & Alerts'),
]

for url, expected_text in endpoints:
    r = client.get(url)
    assert r.status_code == 200, f"Failed on {url}: status {r.status_code}"
    if expected_text:
        content = r.content.decode('utf-8', errors='ignore')
        assert expected_text in content, f"Text '{expected_text}' not in response for {url}"
    print(f"Endpoint {url}: OK (200)")

# 5. Test Excel Exports
for r_type in ['transactions', 'utilization', 'revenue', 'maintenance']:
    export_url = f'/rentals/reports/export/{r_type}/'
    r = client.get(export_url)
    assert r.status_code == 200, f"Failed on export {r_type}: status {r.status_code}"
    assert r['Content-Type'] == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    assert len(r.content) > 1000, f"Excel file too small: {len(r.content)} bytes"
    print(f"Export {r_type} Excel: OK ({len(r.content)} bytes)")

print("\nAll configured endpoint and export checks passed.")
