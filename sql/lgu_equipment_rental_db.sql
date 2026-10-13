-- phpMyAdmin SQL Dump
-- version 5.2.1
-- https://www.phpmyadmin.net/
--
-- Host: 127.0.0.1
-- Generation Time: Oct 13, 2026 at 05:49 PM
-- Server version: 10.4.32-MariaDB
-- PHP Version: 8.2.12

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Database: `lgu_equipment_rental_db`
--

DELIMITER $$
--
-- Procedures
--
CREATE DEFINER=`root`@`localhost` PROCEDURE `sp_check_equipment_availability` (IN `p_equipment_id` INT UNSIGNED, IN `p_start_time` DATETIME, IN `p_end_time` DATETIME)   BEGIN
    DECLARE v_curr_status VARCHAR(50);
    DECLARE v_conflict_count INT DEFAULT 0;
    
    
    SELECT availability_status INTO v_curr_status 
    FROM equipment 
    WHERE equipment_id = p_equipment_id;
    
    
    SELECT COUNT(*) INTO v_conflict_count
    FROM reservations
    WHERE equipment_id = p_equipment_id
      AND status IN ('Scheduled', 'In Progress')
      AND (
          (p_start_time BETWEEN scheduled_start AND scheduled_end)
          OR (p_end_time BETWEEN scheduled_start AND scheduled_end)
          OR (scheduled_start BETWEEN p_start_time AND p_end_time)
      );
      
    SELECT 
        p_equipment_id AS equipment_id,
        v_curr_status AS current_status,
        v_conflict_count AS conflicting_reservations,
        CASE 
            WHEN v_curr_status IN ('Under Maintenance', 'Out of Service') THEN 'UNAVAILABLE_MAINTENANCE'
            WHEN v_conflict_count > 0 THEN 'UNAVAILABLE_CONFLICT'
            ELSE 'AVAILABLE'
        END AS booking_eligibility;
END$$

DELIMITER ;

-- --------------------------------------------------------

--
-- Table structure for table `applicants`
--

CREATE TABLE `applicants` (
  `applicant_id` int(10) UNSIGNED NOT NULL,
  `user_id` int(10) UNSIGNED NOT NULL,
  `applicant_type` enum('Individual','Farmer','Contractor','Organization','Cooperative') NOT NULL,
  `organization_name` varchar(150) DEFAULT NULL,
  `address` text NOT NULL,
  `valid_id_type` varchar(100) DEFAULT NULL,
  `valid_id_number` varchar(100) DEFAULT NULL,
  `tin_number` varchar(50) DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  `updated_at` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Applicant profiles linked to user accounts';



--
-- Table structure for table `audit_logs`
--

CREATE TABLE `audit_logs` (
  `audit_id` int(10) UNSIGNED NOT NULL,
  `user_id` int(10) UNSIGNED DEFAULT NULL,
  `action` varchar(50) NOT NULL COMMENT 'e.g. CREATE, UPDATE, DELETE, LOGIN, LOGOUT, APPROVE, REJECT',
  `table_name` varchar(100) DEFAULT NULL,
  `record_id` int(10) UNSIGNED DEFAULT NULL,
  `details` text DEFAULT NULL,
  `ip_address` varchar(45) DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Audit trail of system activities and security events';




--
-- Table structure for table `equipment`
--

CREATE TABLE `equipment` (
  `equipment_id` int(10) UNSIGNED NOT NULL,
  `category_id` int(10) UNSIGNED NOT NULL,
  `equipment_code` varchar(50) NOT NULL,
  `equipment_name` varchar(150) NOT NULL,
  `brand` varchar(100) DEFAULT NULL,
  `model` varchar(100) DEFAULT NULL,
  `plate_number` varchar(50) DEFAULT NULL,
  `serial_number` varchar(100) DEFAULT NULL,
  `acquisition_date` date DEFAULT NULL,
  `acquisition_cost` decimal(12,2) DEFAULT NULL,
  `condition_status` enum('Excellent','Good','Fair','Needs Repair','Damaged') NOT NULL DEFAULT 'Good',
  `availability_status` enum('Available','Reserved','In Use','Under Maintenance','Out of Service') NOT NULL DEFAULT 'Available',
  `current_location` varchar(255) DEFAULT NULL,
  `photo_url` varchar(255) DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  `updated_at` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Master inventory table for government-owned machinery';


-- --------------------------------------------------------

--
-- Table structure for table `equipment_assignments`
--

CREATE TABLE `equipment_assignments` (
  `assignment_id` int(10) UNSIGNED NOT NULL,
  `reservation_id` int(10) UNSIGNED NOT NULL,
  `equipment_id` int(10) UNSIGNED NOT NULL,
  `operator_id` int(10) UNSIGNED DEFAULT NULL,
  `released_at` datetime DEFAULT NULL,
  `released_by` int(10) UNSIGNED DEFAULT NULL,
  `condition_before` text DEFAULT NULL,
  `returned_at` datetime DEFAULT NULL,
  `received_by` int(10) UNSIGNED DEFAULT NULL,
  `condition_after` text DEFAULT NULL,
  `status` enum('Pending Release','Released','Returned') NOT NULL DEFAULT 'Pending Release',
  `remarks` text DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  `updated_at` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Tracks equipment dispatch, operator assignment, and physical returns';

-- --------------------------------------------------------

--
-- Table structure for table `equipment_categories`
--

CREATE TABLE `equipment_categories` (
  `category_id` int(10) UNSIGNED NOT NULL,
  `category_name` varchar(100) NOT NULL,
  `description` text DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Categories for grouping machinery';


-- --------------------------------------------------------

--
-- Table structure for table `equipment_rates`
--

CREATE TABLE `equipment_rates` (
  `rate_id` int(10) UNSIGNED NOT NULL,
  `equipment_id` int(10) UNSIGNED NOT NULL,
  `rate_amount` decimal(10,2) NOT NULL,
  `rate_unit` enum('Hour','Day','Project') NOT NULL,
  `effective_from` date NOT NULL,
  `effective_to` date DEFAULT NULL,
  `is_active` tinyint(1) NOT NULL DEFAULT 1,
  `notes` varchar(255) DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Rental rates and historical pricing per equipment';


-- --------------------------------------------------------

--
-- Table structure for table `maintenance_records`
--

CREATE TABLE `maintenance_records` (
  `maintenance_id` int(10) UNSIGNED NOT NULL,
  `equipment_id` int(10) UNSIGNED NOT NULL,
  `maintenance_type` enum('Preventive','Repair','Inspection') NOT NULL,
  `problem_reported` text DEFAULT NULL,
  `description` text NOT NULL,
  `technician_name` varchar(150) DEFAULT NULL,
  `cost` decimal(10,2) NOT NULL DEFAULT 0.00,
  `scheduled_date` date NOT NULL,
  `completed_date` date DEFAULT NULL,
  `status` enum('Pending','In Progress','Completed','Cancelled') NOT NULL DEFAULT 'Pending',
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  `updated_at` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Preventive maintenance, inspections, and repair history';


-- --------------------------------------------------------

--
-- Table structure for table `notifications`
--

CREATE TABLE `notifications` (
  `notification_id` int(10) UNSIGNED NOT NULL,
  `user_id` int(10) UNSIGNED NOT NULL,
  `title` varchar(255) NOT NULL,
  `message` text NOT NULL,
  `is_read` tinyint(1) NOT NULL DEFAULT 0,
  `read_at` datetime DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='In-system user notifications and alerts';



--
-- Table structure for table `payments`
--

CREATE TABLE `payments` (
  `payment_id` int(10) UNSIGNED NOT NULL,
  `request_id` int(10) UNSIGNED NOT NULL,
  `amount` decimal(10,2) NOT NULL,
  `payment_type` enum('Rental Fee','Deposit','Refund','Adjustment') NOT NULL,
  `payment_method` enum('Cash','Check','Bank Transfer','Online Payment') NOT NULL DEFAULT 'Cash',
  `reference_or_no` varchar(100) DEFAULT NULL COMMENT 'Official Receipt (OR) Number / Reference No.',
  `payment_status` enum('Pending','Paid','Refunded','Cancelled') NOT NULL DEFAULT 'Paid',
  `payment_date` datetime NOT NULL DEFAULT current_timestamp(),
  `recorded_by` int(10) UNSIGNED NOT NULL,
  `remarks` text DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Financial records for rental fees, deposits, and refunds';


-- --------------------------------------------------------

--
-- Table structure for table `rental_requests`
--

CREATE TABLE `rental_requests` (
  `request_id` int(10) UNSIGNED NOT NULL,
  `applicant_id` int(10) UNSIGNED NOT NULL,
  `purpose` text NOT NULL,
  `project_location` varchar(255) NOT NULL,
  `requested_start` datetime NOT NULL,
  `requested_end` datetime NOT NULL,
  `status` enum('Pending','Under Review','Approved','Rejected','Cancelled','Completed') NOT NULL DEFAULT 'Pending',
  `reviewed_by` int(10) UNSIGNED DEFAULT NULL,
  `reviewed_at` datetime DEFAULT NULL,
  `rejection_reason` text DEFAULT NULL,
  `review_remarks` text DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  `updated_at` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Master table for equipment rental applications';

-------------

--
-- Table structure for table `rental_request_items`
--

CREATE TABLE `rental_request_items` (
  `request_item_id` int(10) UNSIGNED NOT NULL,
  `request_id` int(10) UNSIGNED NOT NULL,
  `equipment_id` int(10) UNSIGNED NOT NULL,
  `quantity` int(10) UNSIGNED NOT NULL DEFAULT 1,
  `estimated_rate` decimal(10,2) DEFAULT NULL,
  `subtotal` decimal(10,2) DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Line items for requested equipment units';


-- --------------------------------------------------------

--
-- Table structure for table `reservations`
--

CREATE TABLE `reservations` (
  `reservation_id` int(10) UNSIGNED NOT NULL,
  `request_id` int(10) UNSIGNED NOT NULL,
  `equipment_id` int(10) UNSIGNED NOT NULL,
  `scheduled_start` datetime NOT NULL,
  `scheduled_end` datetime NOT NULL,
  `approved_by` int(10) UNSIGNED NOT NULL,
  `status` enum('Scheduled','In Progress','Completed','Cancelled','Rescheduled') NOT NULL DEFAULT 'Scheduled',
  `remarks` text DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  `updated_at` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Approved equipment schedules and calendar reservations';


-- --------------------------------------------------------

--
-- Table structure for table `roles`
--

CREATE TABLE `roles` (
  `role_id` int(10) UNSIGNED NOT NULL,
  `role_name` varchar(50) NOT NULL,
  `description` varchar(255) DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Defines system roles and access levels';



-- --------------------------------------------------------

--
-- Table structure for table `users`
--

CREATE TABLE `users` (
  `user_id` int(10) UNSIGNED NOT NULL,
  `role_id` int(10) UNSIGNED NOT NULL,
  `first_name` varchar(100) NOT NULL,
  `last_name` varchar(100) NOT NULL,
  `email` varchar(150) NOT NULL,
  `password_hash` varchar(255) NOT NULL,
  `phone_number` varchar(30) DEFAULT NULL,
  `account_status` enum('Active','Inactive','Suspended') NOT NULL DEFAULT 'Active',
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  `updated_at` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Stores user login accounts and credentials';



-- --------------------------------------------------------

--
-- Table structure for table `utilization_logs`
--

CREATE TABLE `utilization_logs` (
  `utilization_id` int(10) UNSIGNED NOT NULL,
  `assignment_id` int(10) UNSIGNED NOT NULL,
  `usage_date` date NOT NULL,
  `operating_hours` decimal(6,2) NOT NULL DEFAULT 0.00,
  `meter_start` decimal(10,2) DEFAULT NULL,
  `meter_end` decimal(10,2) DEFAULT NULL,
  `fuel_used_liters` decimal(8,2) DEFAULT 0.00,
  `work_description` text NOT NULL,
  `logged_by` int(10) UNSIGNED DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Actual operational logs, engine hours, and fuel consumption';



--
-- Stand-in structure for view `vw_active_reservations`
-- (See below for the actual view)
--
CREATE TABLE `vw_active_reservations` (
`reservation_id` int(10) unsigned
,`request_id` int(10) unsigned
,`equipment_id` int(10) unsigned
,`equipment_code` varchar(50)
,`equipment_name` varchar(150)
,`category_name` varchar(100)
,`scheduled_start` datetime
,`scheduled_end` datetime
,`reservation_status` enum('Scheduled','In Progress','Completed','Cancelled','Rescheduled')
,`applicant_name` varchar(201)
,`organization_name` varchar(150)
,`applicant_phone` varchar(30)
,`project_location` varchar(255)
);

-- --------------------------------------------------------

--
-- Stand-in structure for view `vw_equipment_overview`
-- (See below for the actual view)
--
CREATE TABLE `vw_equipment_overview` (
`equipment_id` int(10) unsigned
,`equipment_code` varchar(50)
,`equipment_name` varchar(150)
,`category_name` varchar(100)
,`brand` varchar(100)
,`model` varchar(100)
,`plate_number` varchar(50)
,`condition_status` enum('Excellent','Good','Fair','Needs Repair','Damaged')
,`availability_status` enum('Available','Reserved','In Use','Under Maintenance','Out of Service')
,`current_location` varchar(255)
,`rate_amount` decimal(10,2)
,`rate_unit` enum('Hour','Day','Project')
);

-- --------------------------------------------------------

--
-- Stand-in structure for view `vw_equipment_utilization_summary`
-- (See below for the actual view)
--
CREATE TABLE `vw_equipment_utilization_summary` (
`equipment_id` int(10) unsigned
,`equipment_code` varchar(50)
,`equipment_name` varchar(150)
,`total_assignments` bigint(21)
,`total_operating_hours` decimal(28,2)
,`total_fuel_liters` decimal(30,2)
);

-- --------------------------------------------------------

--
-- Stand-in structure for view `vw_rental_financial_summary`
-- (See below for the actual view)
--
CREATE TABLE `vw_rental_financial_summary` (
`request_id` int(10) unsigned
,`request_status` enum('Pending','Under Review','Approved','Rejected','Cancelled','Completed')
,`applicant_name` varchar(201)
,`organization_name` varchar(150)
,`total_paid` decimal(32,2)
,`total_deposit` decimal(32,2)
,`total_rental_fees` decimal(32,2)
);

-- --------------------------------------------------------

--
-- Structure for view `vw_active_reservations`
--
DROP TABLE IF EXISTS `vw_active_reservations`;

CREATE ALGORITHM=UNDEFINED DEFINER=`root`@`localhost` SQL SECURITY DEFINER VIEW `vw_active_reservations`  AS SELECT `res`.`reservation_id` AS `reservation_id`, `res`.`request_id` AS `request_id`, `res`.`equipment_id` AS `equipment_id`, `e`.`equipment_code` AS `equipment_code`, `e`.`equipment_name` AS `equipment_name`, `c`.`category_name` AS `category_name`, `res`.`scheduled_start` AS `scheduled_start`, `res`.`scheduled_end` AS `scheduled_end`, `res`.`status` AS `reservation_status`, concat(`u`.`first_name`,' ',`u`.`last_name`) AS `applicant_name`, `app`.`organization_name` AS `organization_name`, `u`.`phone_number` AS `applicant_phone`, `req`.`project_location` AS `project_location` FROM (((((`reservations` `res` join `equipment` `e` on(`res`.`equipment_id` = `e`.`equipment_id`)) join `equipment_categories` `c` on(`e`.`category_id` = `c`.`category_id`)) join `rental_requests` `req` on(`res`.`request_id` = `req`.`request_id`)) join `applicants` `app` on(`req`.`applicant_id` = `app`.`applicant_id`)) join `users` `u` on(`app`.`user_id` = `u`.`user_id`)) ;

-- --------------------------------------------------------

--
-- Structure for view `vw_equipment_overview`
--
DROP TABLE IF EXISTS `vw_equipment_overview`;

CREATE ALGORITHM=UNDEFINED DEFINER=`root`@`localhost` SQL SECURITY DEFINER VIEW `vw_equipment_overview`  AS SELECT `e`.`equipment_id` AS `equipment_id`, `e`.`equipment_code` AS `equipment_code`, `e`.`equipment_name` AS `equipment_name`, `c`.`category_name` AS `category_name`, `e`.`brand` AS `brand`, `e`.`model` AS `model`, `e`.`plate_number` AS `plate_number`, `e`.`condition_status` AS `condition_status`, `e`.`availability_status` AS `availability_status`, `e`.`current_location` AS `current_location`, `r`.`rate_amount` AS `rate_amount`, `r`.`rate_unit` AS `rate_unit` FROM ((`equipment` `e` join `equipment_categories` `c` on(`e`.`category_id` = `c`.`category_id`)) left join `equipment_rates` `r` on(`e`.`equipment_id` = `r`.`equipment_id` and `r`.`is_active` = 1)) ;

-- --------------------------------------------------------

--
-- Structure for view `vw_equipment_utilization_summary`
--
DROP TABLE IF EXISTS `vw_equipment_utilization_summary`;

CREATE ALGORITHM=UNDEFINED DEFINER=`root`@`localhost` SQL SECURITY DEFINER VIEW `vw_equipment_utilization_summary`  AS SELECT `e`.`equipment_id` AS `equipment_id`, `e`.`equipment_code` AS `equipment_code`, `e`.`equipment_name` AS `equipment_name`, count(distinct `ea`.`assignment_id`) AS `total_assignments`, coalesce(sum(`ul`.`operating_hours`),0) AS `total_operating_hours`, coalesce(sum(`ul`.`fuel_used_liters`),0) AS `total_fuel_liters` FROM ((`equipment` `e` left join `equipment_assignments` `ea` on(`e`.`equipment_id` = `ea`.`equipment_id`)) left join `utilization_logs` `ul` on(`ea`.`assignment_id` = `ul`.`assignment_id`)) GROUP BY `e`.`equipment_id`, `e`.`equipment_code`, `e`.`equipment_name` ;

-- --------------------------------------------------------

--
-- Structure for view `vw_rental_financial_summary`
--
DROP TABLE IF EXISTS `vw_rental_financial_summary`;

CREATE ALGORITHM=UNDEFINED DEFINER=`root`@`localhost` SQL SECURITY DEFINER VIEW `vw_rental_financial_summary`  AS SELECT `req`.`request_id` AS `request_id`, `req`.`status` AS `request_status`, concat(`u`.`first_name`,' ',`u`.`last_name`) AS `applicant_name`, `app`.`organization_name` AS `organization_name`, coalesce(sum(`p`.`amount`),0) AS `total_paid`, coalesce(sum(case when `p`.`payment_type` = 'Deposit' then `p`.`amount` else 0 end),0) AS `total_deposit`, coalesce(sum(case when `p`.`payment_type` = 'Rental Fee' then `p`.`amount` else 0 end),0) AS `total_rental_fees` FROM (((`rental_requests` `req` join `applicants` `app` on(`req`.`applicant_id` = `app`.`applicant_id`)) join `users` `u` on(`app`.`user_id` = `u`.`user_id`)) left join `payments` `p` on(`req`.`request_id` = `p`.`request_id` and `p`.`payment_status` = 'Paid')) GROUP BY `req`.`request_id`, `req`.`status`, `u`.`first_name`, `u`.`last_name`, `app`.`organization_name` ;

--
-- Indexes for dumped tables
--

--
-- Indexes for table `applicants`
--
ALTER TABLE `applicants`
  ADD PRIMARY KEY (`applicant_id`),
  ADD UNIQUE KEY `user_id` (`user_id`),
  ADD KEY `idx_applicants_type` (`applicant_type`);

--
-- Indexes for table `audit_logs`
--
ALTER TABLE `audit_logs`
  ADD PRIMARY KEY (`audit_id`),
  ADD KEY `idx_audit_user` (`user_id`),
  ADD KEY `idx_audit_action` (`action`),
  ADD KEY `idx_audit_created` (`created_at`);

--
-- Indexes for table `equipment`
--
ALTER TABLE `equipment`
  ADD PRIMARY KEY (`equipment_id`),
  ADD UNIQUE KEY `equipment_code` (`equipment_code`),
  ADD KEY `idx_equipment_category` (`category_id`),
  ADD KEY `idx_equipment_availability` (`availability_status`),
  ADD KEY `idx_equipment_condition` (`condition_status`);

--
-- Indexes for table `equipment_assignments`
--
ALTER TABLE `equipment_assignments`
  ADD PRIMARY KEY (`assignment_id`),
  ADD KEY `fk_assignments_equipment` (`equipment_id`),
  ADD KEY `fk_assignments_releaser` (`released_by`),
  ADD KEY `fk_assignments_receiver` (`received_by`),
  ADD KEY `idx_assignments_reservation` (`reservation_id`),
  ADD KEY `idx_assignments_operator` (`operator_id`),
  ADD KEY `idx_assignments_status` (`status`);

--
-- Indexes for table `equipment_categories`
--
ALTER TABLE `equipment_categories`
  ADD PRIMARY KEY (`category_id`),
  ADD UNIQUE KEY `category_name` (`category_name`);

--
-- Indexes for table `equipment_rates`
--
ALTER TABLE `equipment_rates`
  ADD PRIMARY KEY (`rate_id`),
  ADD KEY `idx_rates_equipment` (`equipment_id`),
  ADD KEY `idx_rates_effective` (`effective_from`,`effective_to`);

--
-- Indexes for table `maintenance_records`
--
ALTER TABLE `maintenance_records`
  ADD PRIMARY KEY (`maintenance_id`),
  ADD KEY `idx_maintenance_equipment` (`equipment_id`),
  ADD KEY `idx_maintenance_status` (`status`),
  ADD KEY `idx_maintenance_dates` (`scheduled_date`,`completed_date`);

--
-- Indexes for table `notifications`
--
ALTER TABLE `notifications`
  ADD PRIMARY KEY (`notification_id`),
  ADD KEY `idx_notifications_user_unread` (`user_id`,`is_read`);

--
-- Indexes for table `payments`
--
ALTER TABLE `payments`
  ADD PRIMARY KEY (`payment_id`),
  ADD KEY `fk_payments_recorder` (`recorded_by`),
  ADD KEY `idx_payments_request` (`request_id`),
  ADD KEY `idx_payments_type` (`payment_type`),
  ADD KEY `idx_payments_status` (`payment_status`),
  ADD KEY `idx_payments_or_no` (`reference_or_no`);

--
-- Indexes for table `rental_requests`
--
ALTER TABLE `rental_requests`
  ADD PRIMARY KEY (`request_id`),
  ADD KEY `fk_requests_reviewer` (`reviewed_by`),
  ADD KEY `idx_requests_applicant` (`applicant_id`),
  ADD KEY `idx_requests_status` (`status`),
  ADD KEY `idx_requests_dates` (`requested_start`,`requested_end`);

--
-- Indexes for table `rental_request_items`
--
ALTER TABLE `rental_request_items`
  ADD PRIMARY KEY (`request_item_id`),
  ADD KEY `idx_request_items_request` (`request_id`),
  ADD KEY `idx_request_items_equipment` (`equipment_id`);

--
-- Indexes for table `reservations`
--
ALTER TABLE `reservations`
  ADD PRIMARY KEY (`reservation_id`),
  ADD KEY `fk_reservations_request` (`request_id`),
  ADD KEY `fk_reservations_approver` (`approved_by`),
  ADD KEY `idx_reservations_equipment_dates` (`equipment_id`,`scheduled_start`,`scheduled_end`),
  ADD KEY `idx_reservations_status` (`status`);

--
-- Indexes for table `roles`
--
ALTER TABLE `roles`
  ADD PRIMARY KEY (`role_id`),
  ADD UNIQUE KEY `role_name` (`role_name`);

--
-- Indexes for table `users`
--
ALTER TABLE `users`
  ADD PRIMARY KEY (`user_id`),
  ADD UNIQUE KEY `email` (`email`),
  ADD KEY `idx_users_role` (`role_id`),
  ADD KEY `idx_users_email` (`email`),
  ADD KEY `idx_users_status` (`account_status`);

--
-- Indexes for table `utilization_logs`
--
ALTER TABLE `utilization_logs`
  ADD PRIMARY KEY (`utilization_id`),
  ADD KEY `fk_utilization_logger` (`logged_by`),
  ADD KEY `idx_utilization_assignment` (`assignment_id`),
  ADD KEY `idx_utilization_date` (`usage_date`);

--
-- AUTO_INCREMENT for dumped tables
--

--
-- AUTO_INCREMENT for table `applicants`
--
ALTER TABLE `applicants`
  MODIFY `applicant_id` int(10) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=4;

--
-- AUTO_INCREMENT for table `audit_logs`
--
ALTER TABLE `audit_logs`
  MODIFY `audit_id` int(10) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=7;

--
-- AUTO_INCREMENT for table `equipment`
--
ALTER TABLE `equipment`
  MODIFY `equipment_id` int(10) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=7;

--
-- AUTO_INCREMENT for table `equipment_assignments`
--
ALTER TABLE `equipment_assignments`
  MODIFY `assignment_id` int(10) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=3;

--
-- AUTO_INCREMENT for table `equipment_categories`
--
ALTER TABLE `equipment_categories`
  MODIFY `category_id` int(10) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=6;

--
-- AUTO_INCREMENT for table `equipment_rates`
--
ALTER TABLE `equipment_rates`
  MODIFY `rate_id` int(10) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=10;

--
-- AUTO_INCREMENT for table `maintenance_records`
--
ALTER TABLE `maintenance_records`
  MODIFY `maintenance_id` int(10) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=4;

--
-- AUTO_INCREMENT for table `notifications`
--
ALTER TABLE `notifications`
  MODIFY `notification_id` int(10) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=5;

--
-- AUTO_INCREMENT for table `payments`
--
ALTER TABLE `payments`
  MODIFY `payment_id` int(10) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=5;

--
-- AUTO_INCREMENT for table `rental_requests`
--
ALTER TABLE `rental_requests`
  MODIFY `request_id` int(10) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=4;

--
-- AUTO_INCREMENT for table `rental_request_items`
--
ALTER TABLE `rental_request_items`
  MODIFY `request_item_id` int(10) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=5;

--
-- AUTO_INCREMENT for table `reservations`
--
ALTER TABLE `reservations`
  MODIFY `reservation_id` int(10) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=4;

--
-- AUTO_INCREMENT for table `roles`
--
ALTER TABLE `roles`
  MODIFY `role_id` int(10) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=6;

--
-- AUTO_INCREMENT for table `users`
--
ALTER TABLE `users`
  MODIFY `user_id` int(10) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=9;

--
-- AUTO_INCREMENT for table `utilization_logs`
--
ALTER TABLE `utilization_logs`
  MODIFY `utilization_id` int(10) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=3;

--
-- Constraints for dumped tables
--

--
-- Constraints for table `applicants`
--
ALTER TABLE `applicants`
  ADD CONSTRAINT `fk_applicants_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE ON UPDATE CASCADE;

--
-- Constraints for table `audit_logs`
--
ALTER TABLE `audit_logs`
  ADD CONSTRAINT `fk_audit_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE SET NULL ON UPDATE CASCADE;

--
-- Constraints for table `equipment`
--
ALTER TABLE `equipment`
  ADD CONSTRAINT `fk_equipment_category` FOREIGN KEY (`category_id`) REFERENCES `equipment_categories` (`category_id`) ON UPDATE CASCADE;

--
-- Constraints for table `equipment_assignments`
--
ALTER TABLE `equipment_assignments`
  ADD CONSTRAINT `fk_assignments_equipment` FOREIGN KEY (`equipment_id`) REFERENCES `equipment` (`equipment_id`) ON UPDATE CASCADE,
  ADD CONSTRAINT `fk_assignments_operator` FOREIGN KEY (`operator_id`) REFERENCES `users` (`user_id`) ON DELETE SET NULL ON UPDATE CASCADE,
  ADD CONSTRAINT `fk_assignments_receiver` FOREIGN KEY (`received_by`) REFERENCES `users` (`user_id`) ON DELETE SET NULL ON UPDATE CASCADE,
  ADD CONSTRAINT `fk_assignments_releaser` FOREIGN KEY (`released_by`) REFERENCES `users` (`user_id`) ON DELETE SET NULL ON UPDATE CASCADE,
  ADD CONSTRAINT `fk_assignments_reservation` FOREIGN KEY (`reservation_id`) REFERENCES `reservations` (`reservation_id`) ON UPDATE CASCADE;

--
-- Constraints for table `equipment_rates`
--
ALTER TABLE `equipment_rates`
  ADD CONSTRAINT `fk_rates_equipment` FOREIGN KEY (`equipment_id`) REFERENCES `equipment` (`equipment_id`) ON DELETE CASCADE ON UPDATE CASCADE;

--
-- Constraints for table `maintenance_records`
--
ALTER TABLE `maintenance_records`
  ADD CONSTRAINT `fk_maintenance_equipment` FOREIGN KEY (`equipment_id`) REFERENCES `equipment` (`equipment_id`) ON UPDATE CASCADE;

--
-- Constraints for table `notifications`
--
ALTER TABLE `notifications`
  ADD CONSTRAINT `fk_notifications_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE ON UPDATE CASCADE;

--
-- Constraints for table `payments`
--
ALTER TABLE `payments`
  ADD CONSTRAINT `fk_payments_recorder` FOREIGN KEY (`recorded_by`) REFERENCES `users` (`user_id`) ON UPDATE CASCADE,
  ADD CONSTRAINT `fk_payments_request` FOREIGN KEY (`request_id`) REFERENCES `rental_requests` (`request_id`) ON UPDATE CASCADE;

--
-- Constraints for table `rental_requests`
--
ALTER TABLE `rental_requests`
  ADD CONSTRAINT `fk_requests_applicant` FOREIGN KEY (`applicant_id`) REFERENCES `applicants` (`applicant_id`) ON UPDATE CASCADE,
  ADD CONSTRAINT `fk_requests_reviewer` FOREIGN KEY (`reviewed_by`) REFERENCES `users` (`user_id`) ON DELETE SET NULL ON UPDATE CASCADE;

--
-- Constraints for table `rental_request_items`
--
ALTER TABLE `rental_request_items`
  ADD CONSTRAINT `fk_request_items_equipment` FOREIGN KEY (`equipment_id`) REFERENCES `equipment` (`equipment_id`) ON UPDATE CASCADE,
  ADD CONSTRAINT `fk_request_items_request` FOREIGN KEY (`request_id`) REFERENCES `rental_requests` (`request_id`) ON DELETE CASCADE ON UPDATE CASCADE;

--
-- Constraints for table `reservations`
--
ALTER TABLE `reservations`
  ADD CONSTRAINT `fk_reservations_approver` FOREIGN KEY (`approved_by`) REFERENCES `users` (`user_id`) ON UPDATE CASCADE,
  ADD CONSTRAINT `fk_reservations_equipment` FOREIGN KEY (`equipment_id`) REFERENCES `equipment` (`equipment_id`) ON UPDATE CASCADE,
  ADD CONSTRAINT `fk_reservations_request` FOREIGN KEY (`request_id`) REFERENCES `rental_requests` (`request_id`) ON UPDATE CASCADE;

--
-- Constraints for table `users`
--
ALTER TABLE `users`
  ADD CONSTRAINT `fk_users_role` FOREIGN KEY (`role_id`) REFERENCES `roles` (`role_id`) ON UPDATE CASCADE;

--
-- Constraints for table `utilization_logs`
--
ALTER TABLE `utilization_logs`
  ADD CONSTRAINT `fk_utilization_assignment` FOREIGN KEY (`assignment_id`) REFERENCES `equipment_assignments` (`assignment_id`) ON DELETE CASCADE ON UPDATE CASCADE,
  ADD CONSTRAINT `fk_utilization_logger` FOREIGN KEY (`logged_by`) REFERENCES `users` (`user_id`) ON DELETE SET NULL ON UPDATE CASCADE;
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
