from decimal import Decimal
from django.conf import settings
from django.db import models
from django.utils import timezone


class Role(models.Model):
    id = models.BigAutoField(primary_key=True)
    role_name = models.CharField(max_length=50)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = True
        db_table = 'tbl_roles'

    def __str__(self):
        return self.role_name


class Applicant(models.Model):
    id = models.BigAutoField(primary_key=True)
    applicant_type = models.CharField(max_length=50, default='Individual')  # Farmer, Contractor, Resident, Cooperative, Individual
    organization_name = models.CharField(max_length=255, blank=True, null=True)
    address = models.CharField(max_length=255)
    valid_id_type = models.CharField(max_length=100)
    valid_id_number = models.CharField(max_length=100)
    tin_number = models.CharField(max_length=50, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, db_column='user_id', related_name='applicant_profile')

    class Meta:
        managed = True
        db_table = 'tbl_applicants'

    def __str__(self):
        name = self.user.get_full_name() or self.user.username
        if self.organization_name:
            return f"{name} ({self.organization_name})"
        return name

    @property
    def display_name(self):
        return self.user.get_full_name() or self.user.username


class EquipmentCategory(models.Model):
    id = models.BigAutoField(primary_key=True)
    category_name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = True
        db_table = 'tbl_equipment_categories'

    def __str__(self):
        return self.category_name


class Equipment(models.Model):
    AVAILABILITY_CHOICES = (
        ('Available', 'Available'),
        ('Reserved', 'Reserved'),
        ('In Use', 'In Use'),
        ('Under Maintenance', 'Under Maintenance'),
        ('Out of Service', 'Out of Service'),
    )
    CONDITION_CHOICES = (
        ('Excellent', 'Excellent'),
        ('Good', 'Good'),
        ('Fair', 'Fair'),
        ('Needs Repair', 'Needs Repair'),
    )

    id = models.BigAutoField(primary_key=True)
    equipment_code = models.CharField(max_length=50, unique=True)
    equipment_name = models.CharField(max_length=255)
    brand = models.CharField(max_length=100, blank=True, null=True)
    model = models.CharField(max_length=100, blank=True, null=True)
    plate_number = models.CharField(max_length=50, blank=True, null=True)
    serial_number = models.CharField(max_length=100, blank=True, null=True)
    acquisition_date = models.DateField(blank=True, null=True)
    acquisition_cost = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    condition_status = models.CharField(max_length=30, default='Good')
    availability_status = models.CharField(max_length=30, default='Available')
    current_location = models.CharField(max_length=255, blank=True, null=True)
    photo = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    category = models.ForeignKey(EquipmentCategory, on_delete=models.PROTECT, db_column='category_id', related_name='equipment_set')

    class Meta:
        managed = True
        db_table = 'tbl_equipment'
        ordering = ['equipment_name']

    def __str__(self):
        return f"[{self.equipment_code}] {self.equipment_name}"

    @property
    def active_rate(self):
        rate = self.rates.filter(is_active=1).order_by('-effective_from').first()
        return rate

    @property
    def display_rate(self):
        rate = self.active_rate
        if rate:
            return f"₱{rate.rate_amount:,.2f} / {rate.rate_unit}"
        return "No rate set"

    @property
    def status_badge_class(self):
        status = (self.availability_status or '').strip().lower()
        if status == 'available':
            return 'bg-success-lt text-success'
        elif status == 'in use':
            return 'bg-primary-lt text-primary'
        elif status == 'reserved':
            return 'bg-warning-lt text-warning'
        elif status == 'under maintenance':
            return 'bg-danger-lt text-danger'
        return 'bg-secondary-lt text-secondary'

    @property
    def condition_badge_class(self):
        cond = (self.condition_status or '').strip().lower()
        if cond in ['excellent', 'good']:
            return 'bg-teal-lt text-teal'
        elif cond == 'fair':
            return 'bg-yellow-lt text-warning'
        return 'bg-danger-lt text-danger'

    def is_available_for_dates(self, start_dt, end_dt, exclude_reservation_id=None):
        """Check whether this equipment has overlapping active reservations or maintenance."""
        if self.availability_status in ['Under Maintenance', 'Out of Service']:
            return False, f"Equipment is currently {self.availability_status}."

        qs = self.reservations.filter(
            status__in=['Scheduled', 'In Progress'],
            scheduled_start__lt=end_dt,
            scheduled_end__gt=start_dt,
        )
        if exclude_reservation_id:
            qs = qs.exclude(id=exclude_reservation_id)

        if qs.exists():
            conflict = qs.first()
            return False, f"Already reserved from {conflict.scheduled_start:%b %d, %Y %I:%M %p} to {conflict.scheduled_end:%b %d, %Y %I:%M %p}."

        return True, "Available"


class EquipmentRate(models.Model):
    id = models.BigAutoField(primary_key=True)
    rate_amount = models.DecimalField(max_digits=10, decimal_places=2)
    rate_unit = models.CharField(max_length=20, default='Day')  # Hour, Day, Month, Project
    effective_from = models.DateField(default=timezone.now)
    effective_to = models.DateField(blank=True, null=True)
    is_active = models.IntegerField(default=1)
    notes = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    equipment = models.ForeignKey(Equipment, on_delete=models.CASCADE, db_column='equipment_id', related_name='rates')

    class Meta:
        managed = True
        db_table = 'tbl_equipment_rates'

    def __str__(self):
        return f"{self.equipment.equipment_code}: ₱{self.rate_amount:,.2f}/{self.rate_unit}"


class RentalRequest(models.Model):
    STATUS_CHOICES = (
        ('Pending', 'Pending Review'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
        ('Scheduled', 'Scheduled'),
        ('Released', 'Released (In Use)'),
        ('Returned', 'Returned'),
        ('Completed', 'Completed'),
        ('Cancelled', 'Cancelled'),
    )

    id = models.BigAutoField(primary_key=True)
    purpose = models.TextField()
    project_location = models.CharField(max_length=255)
    requested_start = models.DateTimeField()
    requested_end = models.DateTimeField()
    status = models.CharField(max_length=30, default='Pending')
    reviewed_at = models.DateTimeField(blank=True, null=True)
    rejection_reason = models.TextField(blank=True, null=True)
    review_remarks = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    applicant = models.ForeignKey(Applicant, on_delete=models.CASCADE, db_column='applicant_id', related_name='requests')
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, db_column='reviewed_by_id', related_name='reviewed_rental_requests')

    class Meta:
        managed = True
        db_table = 'tbl_rental_requests'
        ordering = ['-created_at']

    def __str__(self):
        return f"REQ-#{self.id:04d} - {self.applicant.display_name} ({self.status})"

    @property
    def total_estimated_cost(self):
        return sum((item.subtotal or Decimal('0.00')) for item in self.items.all())

    @property
    def total_paid(self):
        paid_qs = self.payments.filter(payment_status='Paid')
        return sum(p.amount for p in paid_qs)

    @property
    def balance_due(self):
        return max(Decimal('0.00'), self.total_estimated_cost - self.total_paid)

    @property
    def is_fully_paid(self):
        return self.total_estimated_cost > 0 and self.total_paid >= self.total_estimated_cost

    @property
    def status_badge_class(self):
        s = (self.status or '').strip().lower()
        if s == 'pending':
            return 'bg-warning-lt text-warning'
        elif s == 'approved':
            return 'bg-primary-lt text-primary'
        elif s in ['scheduled', 'released']:
            return 'bg-azure-lt text-azure'
        elif s in ['returned', 'completed']:
            return 'bg-success-lt text-success'
        elif s in ['rejected', 'cancelled']:
            return 'bg-danger-lt text-danger'
        return 'bg-secondary-lt text-secondary'

    @property
    def duration_days(self):
        if self.requested_start and self.requested_end:
            diff = self.requested_end - self.requested_start
            days = max(1, diff.days + (1 if diff.seconds > 0 else 0))
            return days
        return 1


class RentalRequestItem(models.Model):
    id = models.BigAutoField(primary_key=True)
    quantity = models.PositiveIntegerField(default=1)
    estimated_rate = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    equipment = models.ForeignKey(Equipment, on_delete=models.PROTECT, db_column='equipment_id', related_name='request_items')
    request = models.ForeignKey(RentalRequest, on_delete=models.CASCADE, db_column='request_id', related_name='items')

    class Meta:
        managed = True
        db_table = 'tbl_rental_request_items'

    def __str__(self):
        return f"{self.equipment.equipment_name} for REQ-#{self.request_id}"


class Reservation(models.Model):
    STATUS_CHOICES = (
        ('Scheduled', 'Scheduled'),
        ('In Progress', 'In Progress'),
        ('Completed', 'Completed'),
        ('Cancelled', 'Cancelled'),
    )

    id = models.BigAutoField(primary_key=True)
    scheduled_start = models.DateTimeField()
    scheduled_end = models.DateTimeField()
    status = models.CharField(max_length=30, default='Scheduled')
    remarks = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, db_column='approved_by_id', related_name='approved_reservations')
    equipment = models.ForeignKey(Equipment, on_delete=models.PROTECT, db_column='equipment_id', related_name='reservations')
    request = models.ForeignKey(RentalRequest, on_delete=models.CASCADE, db_column='request_id', related_name='reservations')

    class Meta:
        managed = True
        db_table = 'tbl_reservations'
        ordering = ['-scheduled_start']

    def __str__(self):
        return f"RES-#{self.id:04d}: {self.equipment.equipment_code} ({self.status})"

    @property
    def status_badge_class(self):
        s = (self.status or '').strip().lower()
        if s == 'scheduled':
            return 'bg-warning-lt text-warning'
        elif s == 'in progress':
            return 'bg-primary-lt text-primary'
        elif s == 'completed':
            return 'bg-success-lt text-success'
        return 'bg-danger-lt text-danger'


class EquipmentAssignment(models.Model):
    STATUS_CHOICES = (
        ('Pending Release', 'Pending Release'),
        ('Released', 'Released (Active Deployment)'),
        ('Returned', 'Returned (Inspected)'),
        ('Cancelled', 'Cancelled'),
    )

    id = models.BigAutoField(primary_key=True)
    released_at = models.DateTimeField(blank=True, null=True)
    condition_before = models.TextField(blank=True, null=True)
    returned_at = models.DateTimeField(blank=True, null=True)
    condition_after = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=30, default='Pending Release')
    remarks = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    equipment = models.ForeignKey(Equipment, on_delete=models.PROTECT, db_column='equipment_id', related_name='assignments')
    operator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, db_column='operator_id', related_name='operator_assignments')
    released_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, db_column='released_by_id', related_name='released_assignments')
    received_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, db_column='received_by_id', related_name='received_assignments')
    reservation = models.ForeignKey(Reservation, on_delete=models.CASCADE, db_column='reservation_id', related_name='assignments')

    class Meta:
        managed = True
        db_table = 'tbl_equipment_assignments'
        ordering = ['-created_at']

    def __str__(self):
        return f"DEPLOY-#{self.id:04d}: {self.equipment.equipment_code} ({self.status})"

    @property
    def status_badge_class(self):
        s = (self.status or '').strip().lower()
        if 'released' in s:
            return 'bg-primary-lt text-primary'
        elif 'returned' in s:
            return 'bg-success-lt text-success'
        elif 'pending' in s:
            return 'bg-warning-lt text-warning'
        return 'bg-secondary-lt text-secondary'


class UtilizationLog(models.Model):
    id = models.BigAutoField(primary_key=True)
    usage_date = models.DateField(default=timezone.now)
    operating_hours = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0.00'))
    meter_start = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    meter_end = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    fuel_used_liters = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))
    work_description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    assignment = models.ForeignKey(EquipmentAssignment, on_delete=models.CASCADE, db_column='assignment_id', related_name='utilization_logs')
    logged_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, db_column='logged_by_id', related_name='logged_utilizations')

    class Meta:
        managed = True
        db_table = 'tbl_utilization_logs'
        ordering = ['-usage_date', '-created_at']

    def __str__(self):
        return f"Log #{self.id} on {self.usage_date}: {self.operating_hours} hrs, {self.fuel_used_liters} L"


class MaintenanceRecord(models.Model):
    TYPE_CHOICES = (
        ('Preventive', 'Preventive Maintenance'),
        ('Corrective', 'Corrective Repair'),
        ('Emergency', 'Emergency Breakdown Repair'),
        ('Inspection', 'Safety & Routine Inspection'),
    )
    STATUS_CHOICES = (
        ('Scheduled', 'Scheduled'),
        ('In Progress', 'In Progress'),
        ('Completed', 'Completed'),
        ('Cancelled', 'Cancelled'),
    )

    id = models.BigAutoField(primary_key=True)
    maintenance_type = models.CharField(max_length=30, default='Preventive')
    problem_reported = models.TextField(blank=True, null=True)
    description = models.TextField()
    technician_name = models.CharField(max_length=150, blank=True, null=True)
    cost = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    scheduled_date = models.DateField(default=timezone.now)
    completed_date = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=30, default='Scheduled')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    equipment = models.ForeignKey(Equipment, on_delete=models.CASCADE, db_column='equipment_id', related_name='maintenance_records')

    class Meta:
        managed = True
        db_table = 'tbl_maintenance_records'
        ordering = ['-scheduled_date']

    def __str__(self):
        return f"MAINT-#{self.id:04d}: {self.equipment.equipment_code} ({self.maintenance_type})"

    @property
    def status_badge_class(self):
        s = (self.status or '').strip().lower()
        if s == 'completed':
            return 'bg-success-lt text-success'
        elif s == 'in progress':
            return 'bg-warning-lt text-warning'
        elif s == 'scheduled':
            return 'bg-azure-lt text-azure'
        return 'bg-secondary-lt text-secondary'


class Payment(models.Model):
    TYPE_CHOICES = (
        ('Deposit', 'Security Deposit'),
        ('Rental Fee', 'Rental Fee'),
        ('Overtime Fee', 'Overtime Fee'),
        ('Damage Fee', 'Damage / Repair Charge'),
    )
    METHOD_CHOICES = (
        ('Cash', 'Cash (LGU Treasury)'),
        ('Bank Transfer', 'Bank Transfer / Landbank'),
        ('Check', 'Manager / Cashier Check'),
        ('GCash/e-Wallet', 'e-Wallet / GCash'),
    )
    STATUS_CHOICES = (
        ('Paid', 'Paid'),
        ('Pending', 'Pending Verification'),
        ('Refunded', 'Deposit Refunded'),
    )

    id = models.BigAutoField(primary_key=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_type = models.CharField(max_length=30, default='Rental Fee')
    payment_method = models.CharField(max_length=30, default='Cash')
    reference_or_no = models.CharField(max_length=100, blank=True, null=True)
    payment_status = models.CharField(max_length=20, default='Paid')
    payment_date = models.DateTimeField(default=timezone.now)
    remarks = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, db_column='recorded_by_id', related_name='recorded_payments')
    request = models.ForeignKey(RentalRequest, on_delete=models.CASCADE, db_column='request_id', related_name='payments')

    class Meta:
        managed = True
        db_table = 'tbl_payments'
        ordering = ['-payment_date']

    def __str__(self):
        return f"OR #{self.reference_or_no or self.id}: ₱{self.amount:,.2f} ({self.payment_status})"

    @property
    def status_badge_class(self):
        s = (self.payment_status or '').strip().lower()
        if s == 'paid':
            return 'bg-success-lt text-success'
        elif s == 'pending':
            return 'bg-warning-lt text-warning'
        return 'bg-secondary-lt text-secondary'


class Notification(models.Model):
    id = models.BigAutoField(primary_key=True)
    title = models.CharField(max_length=255)
    message = models.TextField()
    is_read = models.IntegerField(default=0)
    read_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, db_column='user_id', related_name='notifications')

    class Meta:
        managed = True
        db_table = 'tbl_notifications'
        ordering = ['-created_at']

    def __str__(self):
        return f"Notification for {self.user.username}: {self.title}"


class AuditLog(models.Model):
    id = models.BigAutoField(primary_key=True)
    action = models.CharField(max_length=50)
    table_name = models.CharField(max_length=100, blank=True, null=True)
    record_id = models.PositiveIntegerField(blank=True, null=True)
    details = models.TextField(blank=True, null=True)
    ip_address = models.CharField(max_length=45, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, db_column='user_id', related_name='audit_logs')

    class Meta:
        managed = True
        db_table = 'tbl_audit_logs'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.action} on {self.table_name} (#{self.record_id})"
