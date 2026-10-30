LGU EQUIPMENT RENTAL SCHEDULING AND UTILIZATION TRACKING SYSTEM:

John Carlo Samblacinio

Jose Emmanuel Servando

Jorem Tabungcay


INTRODUCTION
  
Background of the Project  

Local Government Units (LGU) use equipment such as service vehicles, construction equipment, and other public-use resources to support community projects and services. Managing equipment rentals involves maintaining equipment records, setting rental rates, checking availability, reviewing requests, scheduling approved rentals, recording equipment release and return, and monitoring maintenance and payments.
When these activities are handled through separate or manual records, staff may have difficulty checking schedules, tracking equipment condition, and keeping rental information consistent. Overlapping bookings, incomplete utilization records, and delays in preparing reports may affect the coordination of equipment use.
To address these coordination needs, the proposed project will develop a web-based LGU Equipment Rental Scheduling and Utilization Tracking System. The system will centralize equipment inventory and rental requests, support schedule-conflict checking, and provide records for equipment deployment, return, utilization, maintenance, payment, and reporting. Authorized users will access functions according to their assigned roles.

Statement of the Problem or Project Objectives

The main objective of this project will be to develop a web-based LGU Equipment Rental Scheduling and Utilization Tracking System that will organize equipment rental activities and improve the tracking of equipment use.
The specific objectives of the project will be to:
1. Develop an equipment inventory module that will organize equipment categories, condition, availability, location, and rental rates.
2. Provide a rental request module that will allow applicants to submit equipment, date and time range, purpose, location, and applicant details.
3. Implement a request review and reservation workflow that will check for overlapping bookings and equipment that is under maintenance or out of service.
4. Provide deployment and return tracking that will record equipment release, return condition, operator assignment, and utilization details.
5. Include maintenance and payment records, receipts, notifications, dashboard summaries, and Excel reports for supported operational information.
6. Apply authenticated access and role-based permissions to protect system functions and records.
   
Significance of the Project

LGU Officials and Administrators. The system will provide organized rental and utilization information to support monitoring and administrative decisions.
Equipment Officers. The system will help officers maintain equipment records, review rental applications, manage reservations, coordinate equipment release and return, and record maintenance activities.
Equipment Operators. The system will provide access to assigned deployment information and allow utilization details to be recorded where permitted.
Finance Officers. The system will support recording rental-related payments and generating payment receipts for transactions entered into the system.
Applicants and Community Members. Applicants will be able to browse available equipment, submit rental requests, and monitor the status of their requests through a web browser.

Alignment with Institutional Research Agenda and Sustainable Development Goals

Institutional Research Agenda Alignment. The project may align with an institutional research priority related to Information Technology, digital transformation, information systems, or e-governance. The specific institutional research priority will be confirmed with the school and adviser before submission.
Sustainable Development Goal Alignment. The project may support SDG 9 (Industry, Innovation and Infrastructure) by applying web technology to organize equipment information and rental workflows. It may also support SDG 16 (Peace, Justice and Strong Institutions) by helping maintain traceable records of requests, approvals, equipment use, and transactions. These alignments describe the project's intended contribution and do not claim measured outcomes.

SCOPE AND LIMITATIONS

System Scope & Technical Architecture

The proposed system will support the management of LGU equipment rental activities from request submission through approval, reservation, equipment release and return, utilization recording, payment entry, and report generation. Its intended users will include applicants, Equipment Officers, Equipment Operators, Finance Officers, and system administrators.
Core Modules. The system will include equipment inventory and category management, rental rate records, applicant registration and login, rental request submission and review, reservation scheduling and conflict checking, equipment deployment and return tracking; operator assignment, utilization logs, maintenance records, payment recording and receipts, in-app notifications, dashboard summaries, and Excel report exports.
Technology Stack. The system will use Python and the Django web framework for application processing, Django templates with HTML, CSS, and JavaScript for the user interface, and a MySQL-compatible relational database for data storage. The openpyxl library will be used to support spreadsheet report generation. The final database configuration and schema will be verified before deployment.
Access and Data. Users will access the system through a supported web browser and a configured server. Authentication and role-based permissions will restrict access to designated functions. Stored records will include equipment, applicants, rental requests, reservations, assignments, utilization, maintenance, payments, notifications, and audit-related information.

Limitations

• The system will record payment information and generate receipts, but online payment gateway processing and verification of actual money transfers will not be included unless separately implemented.
• The system will not provide GPS tracking, live vehicle tracking, telematics, or automatic equipment-meter readings. Utilization details, including operating hours, meter readings, and fuel information, will depend on manual entry.
• External email and SMS delivery will not be assumed to be available. The system may record in-app notifications, but successful delivery through external services will require separate integration and testing.
• The project will be accessed through a web browser and will not include a dedicated native Android or iOS application in the current scope.
• Rental fees, eligibility rules, required documents, approval authority, penalties, and data-retention policies will depend on the implementing LGU and will need to be defined and approved by authorized personnel.
• Scheduling accuracy will depend on correct and timely entries for equipment status, requested dates, maintenance periods, and return information. Incorrect or delayed entries may affect displayed availability.
• Before actual deployment, the team will verify database configuration and consistency among the database schema, Django models, and migrations. Security settings, secret management, allowed hosts, HTTPS, backups, and access permissions will also require review.
• Testing will cover selected system functions, but successful testing of selected functions will not by itself establish that every workflow or production scenario has been verified.
