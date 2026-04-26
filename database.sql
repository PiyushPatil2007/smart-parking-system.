-- Step 12: Create Database (run these in MySQL prompt)
CREATE DATABASE IF NOT EXISTS smart_parking;
USE smart_parking;

-- Users Table
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    email VARCHAR(100) NOT NULL UNIQUE,
    role ENUM('user', 'admin') DEFAULT 'user',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    default_vehicle VARCHAR(20) NULL
);

-- Parking Slots Table
CREATE TABLE IF NOT EXISTS parking_slots (
    id INT AUTO_INCREMENT PRIMARY KEY,
    slot_number VARCHAR(10) NOT NULL UNIQUE,
    status ENUM('Available', 'Occupied') DEFAULT 'Available',
    vehicle_type ENUM('Car', 'Bike') NOT NULL
);

-- Bookings Table
CREATE TABLE IF NOT EXISTS bookings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    slot_id INT,
    vehicle_number VARCHAR(20) NOT NULL,
    booking_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    exit_time TIMESTAMP NULL,
    status ENUM('Active', 'Completed') DEFAULT 'Active',
    payment_status ENUM('Pending', 'Paid') DEFAULT 'Pending',
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (slot_id) REFERENCES parking_slots(id)
);

-- Step 14: Add Sample Parking Slots
INSERT IGNORE INTO parking_slots(slot_number,status,vehicle_type)
VALUES
('A01','Available','Car'),
('A02','Available','Car'),
('A03','Available','Car'),
('A04','Available','Car'),
('B01','Available','Bike'),
('B02','Available','Bike'),
('B03','Available','Bike'),
('B04','Available','Bike'),
('C01','Available','Car'),
('C02','Available','Car'),
('C03','Available','Car'),
('C04','Available','Car'),
('D01','Available','Bike'),
('D02','Available','Bike'),
('D03','Available','Bike'),
('D04','Available','Bike'),
('E01','Available','Car'),
('E02','Available','Car'),
('E03','Available','Car'),
('E04','Available','Car');
