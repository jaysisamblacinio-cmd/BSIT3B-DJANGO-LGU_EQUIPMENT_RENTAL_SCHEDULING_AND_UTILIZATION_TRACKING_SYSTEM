from django.urls import path
from . import views

app_name = 'rentals'

urlpatterns = [
    # Equipment
    path('equipment/', views.equipment_list, name='equipment_list'),
    path('equipment/<int:pk>/', views.equipment_detail, name='equipment_detail'),
    path('equipment/ajax/save/', views.equipment_save_ajax, name='equipment_save_ajax'),
    path('equipment/ajax/delete/<int:pk>/', views.equipment_delete_ajax, name='equipment_delete_ajax'),

    # Rental Application Workflow
    path('apply/', views.apply_rental_page, name='apply_rental'),
    path('my-requests/', views.my_requests, name='my_requests'),
    path('requests/', views.requests_list, name='requests_list'),
    path('requests/<int:pk>/action/', views.request_action_ajax, name='request_action_ajax'),
    path('requests/<int:pk>/agreement/', views.rental_agreement_view, name='rental_agreement'),

    # Calendar & Scheduling
    path('calendar/', views.calendar_view, name='calendar'),
    path('calendar/events/', views.calendar_events_api, name='calendar_events_api'),

    # Deployments & Utilization
    path('deployments/', views.deployment_list, name='deployment_list'),
    path('deployments/<int:pk>/release/', views.equipment_release_ajax, name='equipment_release_ajax'),
    path('deployments/<int:pk>/return/', views.equipment_return_ajax, name='equipment_return_ajax'),
    path('utilization/ajax/save/', views.utilization_log_save_ajax, name='utilization_log_save_ajax'),

    # Maintenance
    path('maintenance/', views.maintenance_list, name='maintenance_list'),
    path('maintenance/ajax/save/', views.maintenance_save_ajax, name='maintenance_save_ajax'),

    # Finance & Treasury Payments
    path('payments/', views.payment_list, name='payment_list'),
    path('payments/ajax/save/', views.payment_save_ajax, name='payment_save_ajax'),
    path('payments/<int:pk>/receipt/', views.payment_receipt_view, name='payment_receipt'),

    # Reports & Analytics (Excel)
    path('reports/', views.reports_view, name='reports'),
    path('reports/export/<str:report_type>/', views.export_report_excel, name='export_report_excel'),

    # Notifications
    path('notifications/', views.notifications_list, name='notifications'),
    path('notifications/<int:pk>/read/', views.mark_notification_read_ajax, name='mark_notification_read_ajax'),

    # Demo Role Switcher
    path('switch-role/<str:username>/', views.switch_user_demo, name='switch_user_demo'),
]
