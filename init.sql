SET GLOBAL host_cache_size=0;

CREATE DATABASE IF NOT EXISTS mydb;
USE mydb;

CREATE TABLE IF NOT EXISTS clients (
    tax_id VARCHAR(255) NOT NULL PRIMARY KEY,
    company VARCHAR(255) NOT NULL UNIQUE,
    INDEX(company),
    city VARCHAR(255) NOT NULL,
    postal_code VARCHAR(255) NOT NULL,
    address VARCHAR(255) NOT NULL,
    phone VARCHAR(20) NOT NULL,
    email VARCHAR(255) NOT NULL
);

CREATE TABLE IF NOT EXISTS printers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    serial_number VARCHAR(255) NOT NULL,
    black_counter INT NOT NULL,
    color_counter INT NOT NULL,
    model VARCHAR(255),
    contract_id VARCHAR(255),
    additional_info VARCHAR(255),
    assigned BOOLEAN DEFAULT FALSE,
    tax_id VARCHAR(255),
    service_contract BOOLEAN DEFAULT FALSE,
    lease_rent DECIMAL(10,2),
    price_black DECIMAL(10,2),
    price_color DECIMAL(10,2),
    contract_start_date DATE,
    contract_duration INT,
    warranty BOOLEAN DEFAULT FALSE,
    warranty_duration INT,
    active BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (tax_id) REFERENCES clients(tax_id)
);

CREATE TABLE IF NOT EXISTS print_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    counter_black_history INT,
    counter_color_history INT,
    date DATE,
    printers_id INT,
    FOREIGN KEY (printers_id) REFERENCES printers(id)
);

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    login VARCHAR(255) NOT NULL,
    password VARCHAR(255) NOT NULL,
    admin BOOLEAN NOT NULL,
    email VARCHAR(255)
);

CREATE TABLE my_company (
    id INT AUTO_INCREMENT PRIMARY KEY,
    company_name VARCHAR(255) NOT NULL,
    tax_id VARCHAR(255) NOT NULL UNIQUE,
    address VARCHAR(255) NOT NULL,
    postal_code VARCHAR(10) NOT NULL,
    city VARCHAR(255) NOT NULL,
    phone VARCHAR(20) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS service_requests (
    id INT AUTO_INCREMENT PRIMARY KEY,
    tax_id VARCHAR(255),
    printer_id INT,
    service_request VARCHAR(255),
    assigned_to INT,
    request_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    active BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (tax_id) REFERENCES clients(tax_id),
    FOREIGN KEY (printer_id) REFERENCES printers(id),
    FOREIGN KEY (assigned_to) REFERENCES users(id)
);