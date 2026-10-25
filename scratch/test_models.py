import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.settings')
import django
django.setup()

from apps.rentals.models import (
    Equipment, EquipmentCategory, RentalRequest,
    Reservation, EquipmentAssignment, UtilizationLog,
    MaintenanceRecord, Payment, Applicant
)

print("Equipment count:", Equipment.objects.count())
for eq in Equipment.objects.all():
    print(f" - {eq.equipment_code}: {eq.equipment_name} (Status: {eq.availability_status}, Rate: {eq.display_rate})")

print("\nRental Requests count:", RentalRequest.objects.count())
for r in RentalRequest.objects.all():
    print(f" - REQ #{r.id}: {r.applicant.display_name} -> {r.status} (Total: ₱{r.total_estimated_cost:,.2f}, Paid: ₱{r.total_paid:,.2f})")

print("\nPayments count:", Payment.objects.count())
for p in Payment.objects.all():
    print(f" - OR {p.reference_or_no}: ₱{p.amount:,.2f} ({p.payment_type})")
