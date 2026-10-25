import io
from datetime import datetime, timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Avg, Count, Q, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .models import (
    Applicant, AuditLog, Equipment, EquipmentAssignment, EquipmentCategory,
    EquipmentRate, MaintenanceRecord, Notification, Payment, RentalRequest,
    RentalRequestItem, Reservation, Role, UtilizationLog
)
from .permissions import get_user_role, role_required

User = get_user_model()


def log_audit(user, action, table_name='', record_id=None, details='', request=None):
    """Utility to record administrative audit logs."""
    try:
        ip = ''
        if request:
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip = x_forwarded_for.split(',')[0]
            else:
                ip = request.META.get('REMOTE_ADDR', '')
        AuditLog.objects.create(
            action=action,
            table_name=table_name,
            record_id=record_id,
            details=details,
            ip_address=ip[:45],
            user=user if user and user.is_authenticated else None,
        )
    except Exception:
        pass


def send_notification(user, title, message):
    """Utility to deliver in-app notifications."""
    try:
        Notification.objects.create(
            user=user,
            title=title,
            message=message,
        )
    except Exception:
        pass


# =====================================================================
# DASHBOARD
# =====================================================================

@login_required(login_url='login')
def dashboard_view(request):
    role = get_user_role(request.user)

    total_equipment = Equipment.objects.count()
    available_equipment = Equipment.objects.filter(availability_status='Available').count()
    in_use_equipment = Equipment.objects.filter(availability_status='In Use').count()
    maintenance_equipment = Equipment.objects.filter(availability_status='Under Maintenance').count()
    reserved_equipment = Equipment.objects.filter(availability_status='Reserved').count()

    pending_requests = RentalRequest.objects.filter(status='Pending').count()
    approved_requests = RentalRequest.objects.filter(status='Approved').count()
    active_deployments = EquipmentAssignment.objects.filter(status='Released').count()

    total_revenue = Payment.objects.filter(payment_status='Paid').aggregate(s=Sum('amount'))['s'] or Decimal('0.00')
    total_hours = UtilizationLog.objects.aggregate(s=Sum('operating_hours'))['s'] or Decimal('0.00')
    total_fuel = UtilizationLog.objects.aggregate(s=Sum('fuel_used_liters'))['s'] or Decimal('0.00')

    # Recent items
    recent_requests = RentalRequest.objects.select_related('applicant__user').all()[:8]
    recent_deployments = EquipmentAssignment.objects.select_related('equipment', 'operator', 'reservation').all()[:6]
    maintenance_alerts = MaintenanceRecord.objects.select_related('equipment').filter(
        status__in=['Scheduled', 'In Progress']
    ).order_by('scheduled_date')[:5]

    # Role specific lists
    my_requests = []
    my_assignments = []
    if role == 'Applicant':
        try:
            applicant = request.user.applicant_profile.first()
            if applicant:
                my_requests = RentalRequest.objects.filter(applicant=applicant).order_by('-created_at')[:8]
        except Exception:
            my_requests = []
    elif role == 'Equipment Operator':
        my_assignments = EquipmentAssignment.objects.filter(operator=request.user).order_by('-created_at')[:8]

    # Category breakdown for charts
    categories = EquipmentCategory.objects.annotate(eq_count=Count('equipment_set'))

    context = {
        'page_title': 'Dashboard Overview',
        'role': role,
        'total_equipment': total_equipment,
        'available_equipment': available_equipment,
        'in_use_equipment': in_use_equipment,
        'maintenance_equipment': maintenance_equipment,
        'reserved_equipment': reserved_equipment,
        'pending_requests': pending_requests,
        'approved_requests': approved_requests,
        'active_deployments': active_deployments,
        'total_revenue': total_revenue,
        'total_hours': total_hours,
        'total_fuel': total_fuel,
        'recent_requests': recent_requests,
        'recent_deployments': recent_deployments,
        'maintenance_alerts': maintenance_alerts,
        'my_requests': my_requests,
        'my_assignments': my_assignments,
        'categories': categories,
    }
    return render(request, 'rentals/dashboard.html', context)


# =====================================================================
# DEMO ROLE SWITCHER (For Testing & Evaluator Convenience)
# =====================================================================

@login_required(login_url='login')
def switch_user_demo(request, username):
    """Allows rapid switching between demo roles for capstone presentation."""
    target_user = get_object_or_404(User, username=username)
    login(request, target_user)
    messages.success(request, f"Switched account to {target_user.username} ({get_user_role(target_user)}).")
    return redirect('dashboard')


# =====================================================================
# EQUIPMENT INVENTORY & CATALOG
# =====================================================================

@login_required(login_url='login')
def equipment_list(request):
    role = get_user_role(request.user)
    query = request.GET.get('q', '').strip()
    cat_id = request.GET.get('category', '').strip()
    status = request.GET.get('status', '').strip()

    qs = Equipment.objects.select_related('category').prefetch_related('rates').all()

    if query:
        qs = qs.filter(
            Q(equipment_code__icontains=query) |
            Q(equipment_name__icontains=query) |
            Q(brand__icontains=query) |
            Q(model__icontains=query) |
            Q(plate_number__icontains=query) |
            Q(serial_number__icontains=query) |
            Q(current_location__icontains=query)
        )

    if cat_id:
        qs = qs.filter(category_id=cat_id)

    if status:
        qs = qs.filter(availability_status=status)

    paginator = Paginator(qs, 12)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    categories = EquipmentCategory.objects.all()

    context = {
        'page_title': 'Equipment Catalog & Fleet',
        'equipment_list': page_obj,
        'categories': categories,
        'query': query,
        'selected_category': cat_id,
        'selected_status': status,
        'role': role,
        'status_choices': Equipment.AVAILABILITY_CHOICES,
        'condition_choices': Equipment.CONDITION_CHOICES,
    }
    return render(request, 'rentals/equipment_list.html', context)


@login_required(login_url='login')
def equipment_detail(request, pk):
    role = get_user_role(request.user)
    equipment = get_object_or_404(Equipment.objects.select_related('category'), pk=pk)
    rates = equipment.rates.all().order_by('-is_active', '-effective_from')
    reservations = equipment.reservations.select_related('request__applicant__user', 'approved_by').order_by('-scheduled_start')[:10]
    maintenance_records = equipment.maintenance_records.all().order_by('-scheduled_date')[:10]
    deployments = equipment.assignments.select_related('operator', 'released_by').order_by('-created_at')[:10]

    context = {
        'page_title': f"{equipment.equipment_name} ({equipment.equipment_code})",
        'equipment': equipment,
        'rates': rates,
        'reservations': reservations,
        'maintenance_records': maintenance_records,
        'deployments': deployments,
        'role': role,
    }
    return render(request, 'rentals/equipment_detail.html', context)


@login_required(login_url='login')
@role_required(['Admin', 'Equipment Officer'])
@require_POST
def equipment_save_ajax(request):
    equipment_id = request.POST.get('id')
    code = request.POST.get('equipment_code', '').strip()
    name = request.POST.get('equipment_name', '').strip()
    category_id = request.POST.get('category_id')
    brand = request.POST.get('brand', '').strip()
    model = request.POST.get('model', '').strip()
    plate = request.POST.get('plate_number', '').strip()
    serial = request.POST.get('serial_number', '').strip()
    condition = request.POST.get('condition_status', 'Good')
    availability = request.POST.get('availability_status', 'Available')
    location = request.POST.get('current_location', '').strip()
    rate_amount = request.POST.get('rate_amount', '').strip()
    rate_unit = request.POST.get('rate_unit', 'Day').strip()

    if not code or not name or not category_id:
        return JsonResponse({'error': 'Equipment code, name, and category are required.'}, status=400)

    category = get_object_or_404(EquipmentCategory, pk=category_id)

    # Check code duplicate
    dup_qs = Equipment.objects.filter(equipment_code=code)
    if equipment_id:
        dup_qs = dup_qs.exclude(pk=equipment_id)
    if dup_qs.exists():
        return JsonResponse({'error': f'Equipment code "{code}" is already taken.'}, status=400)

    is_update = bool(equipment_id)
    if is_update:
        equipment = get_object_or_404(Equipment, pk=equipment_id)
    else:
        equipment = Equipment()

    equipment.equipment_code = code
    equipment.equipment_name = name
    equipment.category = category
    equipment.brand = brand
    equipment.model = model
    equipment.plate_number = plate
    equipment.serial_number = serial
    equipment.condition_status = condition
    equipment.availability_status = availability
    equipment.current_location = location
    equipment.save()

    # Rate update or create if provided
    if rate_amount:
        try:
            amt = Decimal(rate_amount)
            # Deactivate old rates if creating new active rate
            equipment.rates.all().update(is_active=0)
            EquipmentRate.objects.create(
                equipment=equipment,
                rate_amount=amt,
                rate_unit=rate_unit,
                is_active=1,
                notes='Standard operational rate',
            )
        except Exception:
            pass

    log_audit(
        request.user,
        'UPDATE' if is_update else 'CREATE',
        'tbl_equipment',
        equipment.id,
        f"{'Updated' if is_update else 'Registered'} equipment {equipment.equipment_code}",
        request,
    )

    messages.success(request, f'Equipment "{equipment.equipment_name}" ({equipment.equipment_code}) has been saved successfully.')
    return JsonResponse({'status': 'success', 'id': equipment.id})


@login_required(login_url='login')
@role_required(['Admin', 'Equipment Officer'])
@require_POST
def equipment_delete_ajax(request, pk):
    equipment = get_object_or_404(Equipment, pk=pk)
    # Check if active in requests or assignments
    if equipment.assignments.filter(status='Released').exists():
        return JsonResponse({'error': 'Cannot delete equipment that is currently deployed in the field.'}, status=400)

    code = equipment.equipment_code
    name = equipment.equipment_name
    equipment.delete()

    log_audit(request.user, 'DELETE', 'tbl_equipment', pk, f"Deleted equipment {code} - {name}", request)
    messages.success(request, f'Equipment "{code} - {name}" has been removed.')
    return JsonResponse({'status': 'deleted'})


# =====================================================================
# RENTAL REQUEST & APPLICANT PORTAL
# =====================================================================

@login_required(login_url='login')
def apply_rental_page(request):
    """Interactive rental application wizard for applicants and officers."""
    role = get_user_role(request.user)
    equipment_list = Equipment.objects.filter(availability_status__in=['Available', 'Reserved', 'In Use']).select_related('category')
    categories = EquipmentCategory.objects.all()

    # Pre-select equipment if query param exists
    preselected_id = request.GET.get('equipment_id')
    preselected_eq = None
    if preselected_id:
        preselected_eq = Equipment.objects.filter(pk=preselected_id).first()

    # Retrieve or initialize applicant profile
    applicant_profile = None
    if request.user.is_authenticated:
        applicant_profile = Applicant.objects.filter(user=request.user).first()

    if request.method == 'POST':
        equipment_ids = request.POST.getlist('equipment_ids')
        start_str = request.POST.get('requested_start')
        end_str = request.POST.get('requested_end')
        purpose = request.POST.get('purpose', '').strip()
        location = request.POST.get('project_location', '').strip()

        # Applicant profile fields
        applicant_type = request.POST.get('applicant_type', 'Individual')
        org_name = request.POST.get('organization_name', '').strip()
        address = request.POST.get('address', '').strip()
        valid_id_type = request.POST.get('valid_id_type', '').strip()
        valid_id_number = request.POST.get('valid_id_number', '').strip()
        tin_number = request.POST.get('tin_number', '').strip()

        if not equipment_ids:
            messages.error(request, 'Please select at least one piece of equipment for rental.')
            return redirect('rentals:apply_rental')

        if not start_str or not end_str:
            messages.error(request, 'Please select both start and end rental dates.')
            return redirect('rentals:apply_rental')

        try:
            start_dt = timezone.datetime.fromisoformat(start_str)
            end_dt = timezone.datetime.fromisoformat(end_str)
            if timezone.is_naive(start_dt):
                start_dt = timezone.make_aware(start_dt)
            if timezone.is_naive(end_dt):
                end_dt = timezone.make_aware(end_dt)
        except Exception:
            messages.error(request, 'Invalid date/time format.')
            return redirect('rentals:apply_rental')

        if end_dt <= start_dt:
            messages.error(request, 'Rental end date must be after the start date.')
            return redirect('rentals:apply_rental')

        if not purpose or not location:
            messages.error(request, 'Please describe the project purpose and delivery location.')
            return redirect('rentals:apply_rental')

        # Create or update applicant profile
        if not applicant_profile:
            applicant_profile = Applicant.objects.create(
                user=request.user,
                applicant_type=applicant_type,
                organization_name=org_name,
                address=address or 'Local Government Area',
                valid_id_type=valid_id_type or "Government ID",
                valid_id_number=valid_id_number or "N/A",
                tin_number=tin_number,
            )
        else:
            if org_name:
                applicant_profile.organization_name = org_name
            if address:
                applicant_profile.address = address
            if valid_id_type:
                applicant_profile.valid_id_type = valid_id_type
            if valid_id_number:
                applicant_profile.valid_id_number = valid_id_number
            if tin_number:
                applicant_profile.tin_number = tin_number
            applicant_profile.save()

        # Check equipment availability
        conflict_errors = []
        selected_equipments = []
        for eq_id in equipment_ids:
            eq = get_object_or_404(Equipment, pk=eq_id)
            is_avail, reason = eq.is_available_for_dates(start_dt, end_dt)
            if not is_avail:
                conflict_errors.append(f"{eq.equipment_code}: {reason}")
            selected_equipments.append(eq)

        if conflict_errors:
            messages.error(request, f"Availability conflict: {'; '.join(conflict_errors)}")
            return redirect('rentals:apply_rental')

        # Calculate estimated duration (in days)
        diff_days = max(1, (end_dt - start_dt).days + (1 if (end_dt - start_dt).seconds > 0 else 0))

        with transaction.atomic():
            rental_request = RentalRequest.objects.create(
                applicant=applicant_profile,
                purpose=purpose,
                project_location=location,
                requested_start=start_dt,
                requested_end=end_dt,
                status='Pending',
            )

            for eq in selected_equipments:
                rate_obj = eq.active_rate
                rate_amt = rate_obj.rate_amount if rate_obj else Decimal('3500.00')
                subtotal = rate_amt * Decimal(diff_days)
                RentalRequestItem.objects.create(
                    request=rental_request,
                    equipment=eq,
                    quantity=1,
                    estimated_rate=rate_amt,
                    subtotal=subtotal,
                )

        # Send notifications to officers
        officers = User.objects.filter(Q(is_superuser=True) | Q(groups__name='Equipment Officer'))
        for off in officers:
            send_notification(
                off,
                f"New Rental Application #{rental_request.id:04d}",
                f"{applicant_profile.display_name} submitted a request for {', '.join(e.equipment_code for e in selected_equipments)} from {start_dt:%b %d} to {end_dt:%b %d}."
            )

        log_audit(request.user, 'CREATE', 'tbl_rental_requests', rental_request.id, f"Submitted rental request #{rental_request.id}", request)
        messages.success(request, f"Your rental application REQ-#{rental_request.id:04d} has been submitted successfully! The Equipment Office will review your request.")
        return redirect('rentals:my_requests')

    context = {
        'page_title': 'Apply for Equipment Rental',
        'equipment_list': equipment_list,
        'categories': categories,
        'preselected_eq': preselected_eq,
        'applicant_profile': applicant_profile,
        'role': role,
    }
    return render(request, 'rentals/apply.html', context)


@login_required(login_url='login')
def my_requests(request):
    """Applicant's personal rental applications view."""
    role = get_user_role(request.user)
    try:
        applicant = request.user.applicant_profile.first()
    except Exception:
        applicant = None

    if applicant:
        requests_qs = RentalRequest.objects.filter(applicant=applicant).prefetch_related('items__equipment', 'reservations').order_by('-created_at')
    else:
        requests_qs = RentalRequest.objects.none()

    paginator = Paginator(requests_qs, 10)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    context = {
        'page_title': 'My Rental Applications',
        'requests': page_obj,
        'applicant': applicant,
        'role': role,
    }
    return render(request, 'rentals/my_requests.html', context)


@login_required(login_url='login')
def requests_list(request):
    """Management view of all rental requests for Admin, Equipment Officer, and Finance."""
    role = get_user_role(request.user)
    status_filter = request.GET.get('status', '').strip()
    query = request.GET.get('q', '').strip()

    qs = RentalRequest.objects.select_related('applicant__user', 'reviewed_by').prefetch_related('items__equipment', 'payments').all()

    if status_filter:
        qs = qs.filter(status=status_filter)

    if query:
        qs = qs.filter(
            Q(applicant__user__username__icontains=query) |
            Q(applicant__user__first_name__icontains=query) |
            Q(applicant__user__last_name__icontains=query) |
            Q(applicant__organization_name__icontains=query) |
            Q(purpose__icontains=query) |
            Q(project_location__icontains=query)
        )

    paginator = Paginator(qs, 15)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    # Counts for status tabs
    counts = {
        'all': RentalRequest.objects.count(),
        'pending': RentalRequest.objects.filter(status='Pending').count(),
        'approved': RentalRequest.objects.filter(status='Approved').count(),
        'scheduled': RentalRequest.objects.filter(status='Scheduled').count(),
        'released': RentalRequest.objects.filter(status='Released').count(),
        'completed': RentalRequest.objects.filter(status='Completed').count(),
        'rejected': RentalRequest.objects.filter(status='Rejected').count(),
    }

    context = {
        'page_title': 'Rental Requests & Approvals',
        'requests': page_obj,
        'selected_status': status_filter,
        'query': query,
        'counts': counts,
        'role': role,
        'operators': User.objects.filter(Q(groups__name='Equipment Operator') | Q(username__icontains='operator')),
    }
    return render(request, 'rentals/requests_list.html', context)


@login_required(login_url='login')
@role_required(['Admin', 'Equipment Officer'])
@require_POST
def request_action_ajax(request, pk):
    """Approve or Reject a submitted rental request."""
    rental_request = get_object_or_404(RentalRequest.objects.prefetch_related('items__equipment'), pk=pk)
    action = request.POST.get('action')  # approve / reject
    remarks = request.POST.get('remarks', '').strip()
    rejection_reason = request.POST.get('rejection_reason', '').strip()
    operator_id = request.POST.get('operator_id')

    if action == 'approve':
        with transaction.atomic():
            rental_request.status = 'Approved'
            rental_request.reviewed_at = timezone.now()
            rental_request.reviewed_by = request.user
            rental_request.review_remarks = remarks or 'Application verified and approved for scheduling.'
            rental_request.save()

            # Create reservations for each requested equipment item
            for item in rental_request.items.all():
                reservation = Reservation.objects.create(
                    request=rental_request,
                    equipment=item.equipment,
                    scheduled_start=rental_request.requested_start,
                    scheduled_end=rental_request.requested_end,
                    status='Scheduled',
                    approved_by=request.user,
                    remarks=remarks or f'Reservation created for {rental_request.applicant.display_name}',
                )
                item.equipment.availability_status = 'Reserved'
                item.equipment.save()

                # Automatically prepare EquipmentAssignment
                operator = None
                if operator_id:
                    operator = User.objects.filter(pk=operator_id).first()

                EquipmentAssignment.objects.create(
                    reservation=reservation,
                    equipment=item.equipment,
                    operator=operator,
                    status='Pending Release',
                    remarks=f"Scheduled for deployment on {rental_request.requested_start:%b %d, %Y}",
                )

        # Notify applicant
        send_notification(
            rental_request.applicant.user,
            f"Rental Application #{rental_request.id:04d} APPROVED",
            f"Your request has been approved! Reservation is scheduled from {rental_request.requested_start:%b %d} to {rental_request.requested_end:%b %d}."
        )

        log_audit(request.user, 'APPROVE', 'tbl_rental_requests', rental_request.id, f"Approved request #{rental_request.id}", request)
        messages.success(request, f"Request REQ-#{rental_request.id:04d} approved and scheduled successfully.")
        return JsonResponse({'status': 'approved'})

    elif action == 'reject':
        if not rejection_reason:
            return JsonResponse({'error': 'Please provide a clear reason for rejecting this rental request.'}, status=400)

        rental_request.status = 'Rejected'
        rental_request.reviewed_at = timezone.now()
        rental_request.reviewed_by = request.user
        rental_request.rejection_reason = rejection_reason
        rental_request.review_remarks = remarks
        rental_request.save()

        # Notify applicant
        send_notification(
            rental_request.applicant.user,
            f"Rental Application #{rental_request.id:04d} Update",
            f"Your request was not approved. Reason: {rejection_reason}"
        )

        log_audit(request.user, 'REJECT', 'tbl_rental_requests', rental_request.id, f"Rejected request #{rental_request.id}: {rejection_reason}", request)
        messages.success(request, f"Request REQ-#{rental_request.id:04d} rejected.")
        return JsonResponse({'status': 'rejected'})

    return JsonResponse({'error': 'Invalid action specified.'}, status=400)


@login_required(login_url='login')
def rental_agreement_view(request, pk):
    """Printable official LGU Rental Agreement & Contract."""
    rental_request = get_object_or_404(
        RentalRequest.objects.select_related('applicant__user', 'reviewed_by').prefetch_related('items__equipment', 'reservations', 'payments'),
        pk=pk
    )
    context = {
        'page_title': f"Rental Agreement - REQ #{rental_request.id:04d}",
        'req': rental_request,
        'today': timezone.now(),
    }
    return render(request, 'rentals/agreement.html', context)


# =====================================================================
# CALENDAR & SCHEDULING
# =====================================================================

@login_required(login_url='login')
def calendar_view(request):
    role = get_user_role(request.user)
    equipments = Equipment.objects.all()
    categories = EquipmentCategory.objects.all()

    context = {
        'page_title': 'Equipment Scheduling Calendar',
        'equipments': equipments,
        'categories': categories,
        'role': role,
    }
    return render(request, 'rentals/calendar.html', context)


@login_required(login_url='login')
def calendar_events_api(request):
    """JSON feed for interactive scheduling calendar."""
    events = []

    # 1. Reservations
    reservations = Reservation.objects.select_related('equipment', 'request__applicant__user').all()
    for res in reservations:
        applicant_name = res.request.applicant.display_name if res.request and res.request.applicant else 'Reserved'
        events.append({
            'id': f"res_{res.id}",
            'title': f"[{res.equipment.equipment_code}] {applicant_name}",
            'start': res.scheduled_start.isoformat(),
            'end': res.scheduled_end.isoformat(),
            'color': '#206bc4' if res.status == 'In Progress' else '#f59f00',
            'url': f"/rentals/equipment/{res.equipment_id}/",
            'extendedProps': {
                'equipment': res.equipment.equipment_name,
                'status': res.status,
                'location': res.request.project_location if res.request else '',
                'type': 'Reservation'
            }
        })

    # 2. Maintenance schedules
    maintenance = MaintenanceRecord.objects.select_related('equipment').all()
    for m in maintenance:
        start_date = m.scheduled_date
        end_date = m.completed_date or (m.scheduled_date + timedelta(days=1))
        events.append({
            'id': f"maint_{m.id}",
            'title': f"[MAINT] {m.equipment.equipment_code}: {m.maintenance_type}",
            'start': start_date.isoformat(),
            'end': end_date.isoformat(),
            'color': '#d63939',
            'url': f"/rentals/maintenance/",
            'extendedProps': {
                'equipment': m.equipment.equipment_name,
                'status': m.status,
                'type': 'Maintenance'
            }
        })

    return JsonResponse(events, safe=False)


# =====================================================================
# DEPLOYMENTS, INSPECTIONS & UTILIZATION
# =====================================================================

@login_required(login_url='login')
def deployment_list(request):
    role = get_user_role(request.user)
    status_filter = request.GET.get('status', '').strip()
    query = request.GET.get('q', '').strip()

    qs = EquipmentAssignment.objects.select_related(
        'equipment__category', 'operator', 'released_by', 'received_by', 'reservation__request__applicant__user'
    ).prefetch_related('utilization_logs').all()

    if status_filter:
        qs = qs.filter(status=status_filter)

    if query:
        qs = qs.filter(
            Q(equipment__equipment_code__icontains=query) |
            Q(equipment__equipment_name__icontains=query) |
            Q(operator__username__icontains=query) |
            Q(operator__first_name__icontains=query) |
            Q(operator__last_name__icontains=query) |
            Q(remarks__icontains=query)
        )

    # If role is Operator, optionally prioritize or highlight operator's own
    paginator = Paginator(qs, 15)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    operators = User.objects.filter(Q(groups__name='Equipment Operator') | Q(username__icontains='operator'))

    context = {
        'page_title': 'Equipment Deployments & Utilization',
        'assignments': page_obj,
        'selected_status': status_filter,
        'query': query,
        'operators': operators,
        'role': role,
    }
    return render(request, 'rentals/deployments.html', context)


@login_required(login_url='login')
@role_required(['Admin', 'Equipment Officer'])
@require_POST
def equipment_release_ajax(request, pk):
    """Release equipment to field: record release inspection, meter start, update status."""
    assignment = get_object_or_404(EquipmentAssignment.objects.select_related('equipment', 'reservation'), pk=pk)
    condition_before = request.POST.get('condition_before', '').strip()
    operator_id = request.POST.get('operator_id')
    remarks = request.POST.get('remarks', '').strip()

    with transaction.atomic():
        assignment.status = 'Released'
        assignment.released_at = timezone.now()
        assignment.released_by = request.user
        assignment.condition_before = condition_before or 'Equipment checked and released in good running condition.'
        if operator_id:
            assignment.operator = User.objects.filter(pk=operator_id).first()
        if remarks:
            assignment.remarks = remarks
        assignment.save()

        # Update machinery and reservation status
        assignment.equipment.availability_status = 'In Use'
        assignment.equipment.save()

        assignment.reservation.status = 'In Progress'
        assignment.reservation.save()

        if assignment.reservation.request:
            assignment.reservation.request.status = 'Released'
            assignment.reservation.request.save()

    log_audit(request.user, 'RELEASE', 'tbl_equipment_assignments', assignment.id, f"Released {assignment.equipment.equipment_code}", request)
    messages.success(request, f"Equipment {assignment.equipment.equipment_code} has been successfully released into the field.")
    return JsonResponse({'status': 'released'})


@login_required(login_url='login')
@role_required(['Admin', 'Equipment Officer'])
@require_POST
def equipment_return_ajax(request, pk):
    """Return equipment from field: post-inspection, check damages, record meter end & hours."""
    assignment = get_object_or_404(EquipmentAssignment.objects.select_related('equipment', 'reservation'), pk=pk)
    condition_after = request.POST.get('condition_after', '').strip()
    equipment_condition = request.POST.get('equipment_condition', 'Good')
    operating_hours = request.POST.get('operating_hours', '0')
    fuel_liters = request.POST.get('fuel_used_liters', '0')
    work_description = request.POST.get('work_description', '').strip()
    remarks = request.POST.get('remarks', '').strip()

    with transaction.atomic():
        assignment.status = 'Returned'
        assignment.returned_at = timezone.now()
        assignment.received_by = request.user
        assignment.condition_after = condition_after or 'Equipment returned and inspected.'
        if remarks:
            assignment.remarks = f"{assignment.remarks or ''}\nReturn Note: {remarks}".strip()
        assignment.save()

        # Update equipment availability & condition
        if equipment_condition == 'Needs Repair':
            assignment.equipment.availability_status = 'Under Maintenance'
        else:
            assignment.equipment.availability_status = 'Available'
        assignment.equipment.condition_status = equipment_condition
        assignment.equipment.save()

        assignment.reservation.status = 'Completed'
        assignment.reservation.save()

        if assignment.reservation.request:
            assignment.reservation.request.status = 'Returned'
            assignment.reservation.request.save()

        # Create utilization log entry
        try:
            hrs = Decimal(operating_hours or '0')
            fuel = Decimal(fuel_liters or '0')
            if hrs > 0 or fuel > 0 or work_description:
                UtilizationLog.objects.create(
                    assignment=assignment,
                    usage_date=timezone.now().date(),
                    operating_hours=hrs,
                    fuel_used_liters=fuel,
                    work_description=work_description or f"Returned from project site at {assignment.reservation.request.project_location if assignment.reservation.request else 'Site'}",
                    logged_by=request.user,
                )
        except Exception:
            pass

    log_audit(request.user, 'RETURN', 'tbl_equipment_assignments', assignment.id, f"Received return of {assignment.equipment.equipment_code}", request)
    messages.success(request, f"Equipment {assignment.equipment.equipment_code} has been returned and inspection logged.")
    return JsonResponse({'status': 'returned'})


@login_required(login_url='login')
@require_POST
def utilization_log_save_ajax(request):
    """Daily engine hour and fuel consumption logger for Operators / Officers."""
    assignment_id = request.POST.get('assignment_id')
    usage_date_str = request.POST.get('usage_date')
    operating_hours = request.POST.get('operating_hours', '0')
    meter_start = request.POST.get('meter_start')
    meter_end = request.POST.get('meter_end')
    fuel_liters = request.POST.get('fuel_used_liters', '0')
    work_description = request.POST.get('work_description', '').strip()

    assignment = get_object_or_404(EquipmentAssignment, pk=assignment_id)

    if not work_description:
        return JsonResponse({'error': 'Please describe the work performed.'}, status=400)

    try:
        hrs = Decimal(operating_hours or '0')
        fuel = Decimal(fuel_liters or '0')
        m_start = Decimal(meter_start) if meter_start else None
        m_end = Decimal(meter_end) if meter_end else None

        # Auto-compute hours if meter start and end are provided
        if m_start is not None and m_end is not None and m_end >= m_start and hrs == 0:
            hrs = m_end - m_start
    except Exception:
        return JsonResponse({'error': 'Invalid numeric values for hours or fuel.'}, status=400)

    usage_date = timezone.now().date()
    if usage_date_str:
        try:
            usage_date = timezone.datetime.fromisoformat(usage_date_str).date()
        except Exception:
            pass

    log = UtilizationLog.objects.create(
        assignment=assignment,
        usage_date=usage_date,
        operating_hours=hrs,
        meter_start=m_start,
        meter_end=m_end,
        fuel_used_liters=fuel,
        work_description=work_description,
        logged_by=request.user,
    )

    log_audit(request.user, 'LOG_UTILIZATION', 'tbl_utilization_logs', log.id, f"Logged {hrs} hrs for {assignment.equipment.equipment_code}", request)
    messages.success(request, f"Utilization log recorded: {hrs} hours and {fuel} L of fuel.")
    return JsonResponse({'status': 'success', 'id': log.id})


# =====================================================================
# MAINTENANCE MANAGEMENT
# =====================================================================

@login_required(login_url='login')
def maintenance_list(request):
    role = get_user_role(request.user)
    status_filter = request.GET.get('status', '').strip()
    query = request.GET.get('q', '').strip()

    qs = MaintenanceRecord.objects.select_related('equipment__category').all()

    if status_filter:
        qs = qs.filter(status=status_filter)

    if query:
        qs = qs.filter(
            Q(equipment__equipment_code__icontains=query) |
            Q(equipment__equipment_name__icontains=query) |
            Q(problem_reported__icontains=query) |
            Q(description__icontains=query) |
            Q(technician_name__icontains=query)
        )

    paginator = Paginator(qs, 12)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    equipments = Equipment.objects.all()

    context = {
        'page_title': 'Maintenance & Servicing Management',
        'records': page_obj,
        'equipments': equipments,
        'selected_status': status_filter,
        'query': query,
        'role': role,
        'type_choices': MaintenanceRecord.TYPE_CHOICES,
        'status_choices': MaintenanceRecord.STATUS_CHOICES,
    }
    return render(request, 'rentals/maintenance.html', context)


@login_required(login_url='login')
@role_required(['Admin', 'Equipment Officer'])
@require_POST
def maintenance_save_ajax(request):
    record_id = request.POST.get('id')
    equipment_id = request.POST.get('equipment_id')
    m_type = request.POST.get('maintenance_type', 'Preventive')
    problem = request.POST.get('problem_reported', '').strip()
    desc = request.POST.get('description', '').strip()
    technician = request.POST.get('technician_name', '').strip()
    cost_str = request.POST.get('cost', '0').strip()
    sched_date_str = request.POST.get('scheduled_date')
    status = request.POST.get('status', 'Scheduled')

    if not equipment_id or not desc:
        return JsonResponse({'error': 'Equipment and service description are required.'}, status=400)

    equipment = get_object_or_404(Equipment, pk=equipment_id)

    try:
        cost = Decimal(cost_str or '0')
    except Exception:
        cost = Decimal('0.00')

    sched_date = timezone.now().date()
    if sched_date_str:
        try:
            sched_date = timezone.datetime.fromisoformat(sched_date_str).date()
        except Exception:
            pass

    is_update = bool(record_id)
    if is_update:
        rec = get_object_or_404(MaintenanceRecord, pk=record_id)
    else:
        rec = MaintenanceRecord()

    rec.equipment = equipment
    rec.maintenance_type = m_type
    rec.problem_reported = problem
    rec.description = desc
    rec.technician_name = technician
    rec.cost = cost
    rec.scheduled_date = sched_date
    rec.status = status

    if status == 'Completed' and not rec.completed_date:
        rec.completed_date = timezone.now().date()
        # Restore equipment status to Available if it was in maintenance
        equipment.availability_status = 'Available'
        equipment.condition_status = 'Good'
        equipment.save()
    elif status in ['Scheduled', 'In Progress']:
        equipment.availability_status = 'Under Maintenance'
        equipment.save()

    rec.save()

    log_audit(request.user, 'MAINTENANCE_UPDATE' if is_update else 'MAINTENANCE_SCHEDULE', 'tbl_maintenance_records', rec.id, f"{m_type} for {equipment.equipment_code}", request)
    messages.success(request, f'Maintenance record for {equipment.equipment_code} has been saved.')
    return JsonResponse({'status': 'success', 'id': rec.id})


# =====================================================================
# FINANCE, PAYMENTS & RECEIPTS
# =====================================================================

@login_required(login_url='login')
def payment_list(request):
    role = get_user_role(request.user)
    query = request.GET.get('q', '').strip()
    type_filter = request.GET.get('type', '').strip()

    qs = Payment.objects.select_related('request__applicant__user', 'recorded_by').all()

    if type_filter:
        qs = qs.filter(payment_type=type_filter)

    if query:
        qs = qs.filter(
            Q(reference_or_no__icontains=query) |
            Q(request__applicant__user__username__icontains=query) |
            Q(request__applicant__organization_name__icontains=query) |
            Q(remarks__icontains=query)
        )

    paginator = Paginator(qs, 15)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    # Totals
    total_paid = Payment.objects.filter(payment_status='Paid').aggregate(s=Sum('amount'))['s'] or Decimal('0.00')
    total_deposits = Payment.objects.filter(payment_type='Deposit', payment_status='Paid').aggregate(s=Sum('amount'))['s'] or Decimal('0.00')
    total_rental_fees = Payment.objects.filter(payment_type='Rental Fee', payment_status='Paid').aggregate(s=Sum('amount'))['s'] or Decimal('0.00')

    active_requests = RentalRequest.objects.filter(status__in=['Approved', 'Scheduled', 'Released']).select_related('applicant__user')

    context = {
        'page_title': 'Rental Payments & Treasury Collections',
        'payments': page_obj,
        'total_paid': total_paid,
        'total_deposits': total_deposits,
        'total_rental_fees': total_rental_fees,
        'active_requests': active_requests,
        'query': query,
        'selected_type': type_filter,
        'role': role,
        'type_choices': Payment.TYPE_CHOICES,
        'method_choices': Payment.METHOD_CHOICES,
    }
    return render(request, 'rentals/payments.html', context)


@login_required(login_url='login')
@role_required(['Admin', 'Finance Officer'])
@require_POST
def payment_save_ajax(request):
    request_id = request.POST.get('request_id')
    amount_str = request.POST.get('amount', '').strip()
    p_type = request.POST.get('payment_type', 'Rental Fee')
    method = request.POST.get('payment_method', 'Cash')
    ref_no = request.POST.get('reference_or_no', '').strip()
    remarks = request.POST.get('remarks', '').strip()

    if not request_id or not amount_str:
        return JsonResponse({'error': 'Rental request and payment amount are required.'}, status=400)

    rental_request = get_object_or_404(RentalRequest, pk=request_id)

    try:
        amount = Decimal(amount_str)
        if amount <= 0:
            return JsonResponse({'error': 'Amount must be greater than zero.'}, status=400)
    except Exception:
        return JsonResponse({'error': 'Enter a valid payment amount.'}, status=400)

    # Generate auto OR number if not provided
    if not ref_no:
        ref_no = f"OR-{timezone.now().year}-{timezone.now().strftime('%m%d')}-{Payment.objects.count() + 1001}"

    payment = Payment.objects.create(
        request=rental_request,
        amount=amount,
        payment_type=p_type,
        payment_method=method,
        reference_or_no=ref_no,
        payment_status='Paid',
        payment_date=timezone.now(),
        remarks=remarks,
        recorded_by=request.user,
    )

    # Send receipt notification to applicant
    send_notification(
        rental_request.applicant.user,
        f"Payment Received: {ref_no}",
        f"Official Receipt issued for ₱{amount:,.2f} ({p_type}) for Request REQ-#{rental_request.id:04d}."
    )

    log_audit(request.user, 'PAYMENT', 'tbl_payments', payment.id, f"Recorded ₱{amount} {ref_no} for REQ #{rental_request.id}", request)
    messages.success(request, f"Official receipt {ref_no} for ₱{amount:,.2f} recorded successfully.")
    return JsonResponse({'status': 'success', 'id': payment.id})


@login_required(login_url='login')
def payment_receipt_view(request, pk):
    """Printable official transaction receipt / Acknowledgement of Payment."""
    payment = get_object_or_404(Payment.objects.select_related('request__applicant__user', 'recorded_by'), pk=pk)
    context = {
        'page_title': f"Receipt #{payment.reference_or_no or payment.id}",
        'payment': payment,
        'req': payment.request,
    }
    return render(request, 'rentals/receipt.html', context)


# =====================================================================
# REPORTS & ANALYTICS & EXCEL EXPORT
# =====================================================================

@login_required(login_url='login')
def reports_view(request):
    role = get_user_role(request.user)

    # Date filters
    today = timezone.now().date()
    start_date = request.GET.get('start_date', (today - timedelta(days=30)).isoformat())
    end_date = request.GET.get('end_date', today.isoformat())

    # Aggregates
    revenue_by_category = Payment.objects.filter(payment_status='Paid').values(
        'request__items__equipment__category__category_name'
    ).annotate(total_collected=Sum('amount')).order_by('-total_collected')

    hours_by_equipment = UtilizationLog.objects.values(
        'assignment__equipment__equipment_code', 'assignment__equipment__equipment_name'
    ).annotate(
        total_hours=Sum('operating_hours'),
        total_fuel=Sum('fuel_used_liters')
    ).order_by('-total_hours')[:8]

    monthly_stats = {
        'total_requests': RentalRequest.objects.count(),
        'approved_requests': RentalRequest.objects.filter(status__in=['Approved', 'Scheduled', 'Released', 'Completed']).count(),
        'total_revenue': Payment.objects.filter(payment_status='Paid').aggregate(s=Sum('amount'))['s'] or Decimal('0.00'),
        'total_maintenance_cost': MaintenanceRecord.objects.aggregate(s=Sum('cost'))['s'] or Decimal('0.00'),
        'total_operating_hours': UtilizationLog.objects.aggregate(s=Sum('operating_hours'))['s'] or Decimal('0.00'),
    }

    recent_logs = UtilizationLog.objects.select_related('assignment__equipment', 'logged_by').order_by('-usage_date')[:10]

    context = {
        'page_title': 'Reports & Utilization Analytics',
        'start_date': start_date,
        'end_date': end_date,
        'monthly_stats': monthly_stats,
        'revenue_by_category': revenue_by_category,
        'hours_by_equipment': hours_by_equipment,
        'recent_logs': recent_logs,
        'role': role,
    }
    return render(request, 'rentals/reports.html', context)


@login_required(login_url='login')
def export_report_excel(request, report_type):
    """Generate professionally styled Excel (.xlsx) reports using openpyxl."""
    wb = openpyxl.Workbook()
    ws = wb.active

    # Brand Header Colors
    navy_fill = PatternFill(start_color="1B2A4A", end_color="1B2A4A", fill_type="solid")
    gold_fill = PatternFill(start_color="F8B84E", end_color="F8B84E", fill_type="solid")
    light_fill = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")

    title_font = Font(name="Segoe UI", size=15, bold=True, color="FFFFFF")
    sub_font = Font(name="Segoe UI", size=10, italic=True, color="E2E8F0")
    header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
    regular_font = Font(name="Segoe UI", size=10)
    bold_font = Font(name="Segoe UI", size=10, bold=True)

    thin_border = Border(
        left=Side(style='thin', color='CBD5E1'),
        right=Side(style='thin', color='CBD5E1'),
        top=Side(style='thin', color='CBD5E1'),
        bottom=Side(style='thin', color='CBD5E1'),
    )

    if report_type == 'transactions':
        ws.title = "Rental Transactions"
        ws.merge_cells("A1:G1")
        ws["A1"] = "LOCAL GOVERNMENT UNIT - EQUIPMENT RENTAL TRANSACTIONS REPORT"
        ws["A1"].font = title_font
        ws["A1"].fill = navy_fill
        ws["A1"].alignment = Alignment(horizontal="center", vertical="center")

        ws.merge_cells("A2:G2")
        ws["A2"] = f"Generated on {timezone.now():%B %d, %Y %I:%M %p} by {request.user.username}"
        ws["A2"].font = sub_font
        ws["A2"].fill = navy_fill
        ws["A2"].alignment = Alignment(horizontal="center", vertical="center")

        headers = ["REQ #", "Applicant", "Organization", "Project Location", "Dates", "Status", "Total Paid"]
        for col_idx, h in enumerate(headers, 1):
            cell = ws.cell(row=4, column=col_idx, value=h)
            cell.font = header_font
            cell.fill = navy_fill
            cell.alignment = Alignment(horizontal="center")

        row_num = 5
        for req in RentalRequest.objects.select_related('applicant__user').prefetch_related('payments').all():
            ws.cell(row=row_num, column=1, value=f"REQ-#{req.id:04d}").font = regular_font
            ws.cell(row=row_num, column=2, value=req.applicant.display_name).font = regular_font
            ws.cell(row=row_num, column=3, value=req.applicant.organization_name or 'Individual').font = regular_font
            ws.cell(row=row_num, column=4, value=req.project_location).font = regular_font
            ws.cell(row=row_num, column=5, value=f"{req.requested_start:%b %d, %Y} - {req.requested_end:%b %d, %Y}").font = regular_font
            ws.cell(row=row_num, column=6, value=req.status).font = bold_font
            ws.cell(row=row_num, column=7, value=float(req.total_paid)).font = regular_font
            row_num += 1

    elif report_type == 'utilization':
        ws.title = "Equipment Utilization"
        ws.merge_cells("A1:F1")
        ws["A1"] = "LGU EQUIPMENT UTILIZATION & FUEL TRACKING REPORT"
        ws["A1"].font = title_font
        ws["A1"].fill = navy_fill
        ws["A1"].alignment = Alignment(horizontal="center", vertical="center")

        headers = ["Date", "Equipment Code", "Equipment Name", "Operating Hours", "Fuel Used (L)", "Work Performed"]
        for col_idx, h in enumerate(headers, 1):
            cell = ws.cell(row=3, column=col_idx, value=h)
            cell.font = header_font
            cell.fill = navy_fill
            cell.alignment = Alignment(horizontal="center")

        row_num = 4
        for log in UtilizationLog.objects.select_related('assignment__equipment').all():
            ws.cell(row=row_num, column=1, value=log.usage_date.strftime("%Y-%m-%d")).font = regular_font
            ws.cell(row=row_num, column=2, value=log.assignment.equipment.equipment_code).font = regular_font
            ws.cell(row=row_num, column=3, value=log.assignment.equipment.equipment_name).font = regular_font
            ws.cell(row=row_num, column=4, value=float(log.operating_hours)).font = bold_font
            ws.cell(row=row_num, column=5, value=float(log.fuel_used_liters)).font = regular_font
            ws.cell(row=row_num, column=6, value=log.work_description).font = regular_font
            row_num += 1

    elif report_type == 'revenue':
        ws.title = "Treasury Collections"
        ws.merge_cells("A1:F1")
        ws["A1"] = "LGU EQUIPMENT RENTAL REVENUE & TREASURY COLLECTIONS REPORT"
        ws["A1"].font = title_font
        ws["A1"].fill = navy_fill
        ws["A1"].alignment = Alignment(horizontal="center", vertical="center")

        headers = ["OR / Ref #", "Payment Date", "Applicant", "Type", "Method", "Amount (PHP)"]
        for col_idx, h in enumerate(headers, 1):
            cell = ws.cell(row=3, column=col_idx, value=h)
            cell.font = header_font
            cell.fill = navy_fill
            cell.alignment = Alignment(horizontal="center")

        row_num = 4
        for p in Payment.objects.select_related('request__applicant__user').all():
            ws.cell(row=row_num, column=1, value=p.reference_or_no or f"OR-{p.id}").font = bold_font
            ws.cell(row=row_num, column=2, value=p.payment_date.strftime("%Y-%m-%d %H:%M")).font = regular_font
            ws.cell(row=row_num, column=3, value=p.request.applicant.display_name if p.request else 'N/A').font = regular_font
            ws.cell(row=row_num, column=4, value=p.payment_type).font = regular_font
            ws.cell(row=row_num, column=5, value=p.payment_method).font = regular_font
            ws.cell(row=row_num, column=6, value=float(p.amount)).font = bold_font
            row_num += 1

    elif report_type == 'maintenance':
        ws.title = "Maintenance Expenses"
        ws.merge_cells("A1:F1")
        ws["A1"] = "LGU EQUIPMENT FLEET MAINTENANCE & REPAIR EXPENSES"
        ws["A1"].font = title_font
        ws["A1"].fill = navy_fill
        ws["A1"].alignment = Alignment(horizontal="center", vertical="center")

        headers = ["Equipment", "Type", "Problem / Reason", "Technician / Shop", "Cost (PHP)", "Status"]
        for col_idx, h in enumerate(headers, 1):
            cell = ws.cell(row=3, column=col_idx, value=h)
            cell.font = header_font
            cell.fill = navy_fill
            cell.alignment = Alignment(horizontal="center")

        row_num = 4
        for m in MaintenanceRecord.objects.select_related('equipment').all():
            ws.cell(row=row_num, column=1, value=f"{m.equipment.equipment_code} - {m.equipment.equipment_name}").font = regular_font
            ws.cell(row=row_num, column=2, value=m.maintenance_type).font = regular_font
            ws.cell(row=row_num, column=3, value=m.description).font = regular_font
            ws.cell(row=row_num, column=4, value=m.technician_name or 'Internal Motorpool').font = regular_font
            ws.cell(row=row_num, column=5, value=float(m.cost)).font = bold_font
            ws.cell(row=row_num, column=6, value=m.status).font = regular_font
            row_num += 1

    # Auto-adjust column widths
    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    filename = f"LGU_Report_{report_type}_{timezone.now():%Y%m%d}.xlsx"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    wb.save(response)
    return response


# =====================================================================
# NOTIFICATIONS API
# =====================================================================

@login_required(login_url='login')
def notifications_list(request):
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')[:30]
    return render(request, 'rentals/notifications.html', {
        'page_title': 'In-System Notifications',
        'notifications': notifications,
    })


@login_required(login_url='login')
@require_POST
def mark_notification_read_ajax(request, pk):
    notif = get_object_or_404(Notification, pk=pk, user=request.user)
    notif.is_read = 1
    notif.read_at = timezone.now()
    notif.save()
    return JsonResponse({'status': 'read'})
