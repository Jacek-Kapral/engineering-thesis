SET GLOBAL host_cache_size=0;

CREATE DATABASE IF NOT EXISTS mydb;
USE mydb;

CREATE TABLE IF NOT EXISTS clients (
    tax_id VARCHAR(255) NOT NULL PRIMARY KEY,
    company VARCHAR(255) NOT NULL,
    INDEX(company),
    city VARCHAR(255) NOT NULL,
    postal_code VARCHAR(255) NOT NULL,
    address VARCHAR(255) NOT NULL,
    phone INT NOT NULL,
    email VARCHAR(255) NOT NULL
);

CREATE TABLE IF NOT EXISTS printers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    serial_number VARCHAR(255) NOT NULL,
    black_counter INT NOT NULL,
    color_counter INT NOT NULL,
    model VARCHAR(255),
    tax_id VARCHAR(255),
    FOREIGN KEY (tax_id) REFERENCES clients(tax_id)
);

CREATE TABLE IF NOT EXISTS contracts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    price_black DECIMAL(10,2),
    price_color DECIMAL(10,2),
    start_date DATE,
    end_date DATE,
    tax_id VARCHAR(255),
    printer_id INT,
    FOREIGN KEY (tax_id) REFERENCES clients(tax_id),
    FOREIGN KEY (printer_id) REFERENCES printers(id)
);

CREATE TABLE IF NOT EXISTS print_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    counter_black_history INT,
    counter_color_history INT,
    date DATE,
    printers_id INT,
    FOREIGN KEY (printers_id) REFERENCES printers(id)
);

CREATE TABLE IF NOT EXISTS models (
    sn_prefix VARCHAR(255) PRIMARY KEY,
    model VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    login VARCHAR(255) NOT NULL,
    password VARCHAR(255) NOT NULL,
    admin BOOLEAN NOT NULL,
    email VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS service_requests (
    id INT AUTO_INCREMENT PRIMARY KEY,
    company VARCHAR(255),
    printer_id INT,
    service_request VARCHAR(255),
    assigned_to INT,
    request_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    active BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (company) REFERENCES clients(company),
    FOREIGN KEY (printer_id) REFERENCES printers(id),
    FOREIGN KEY (assigned_to) REFERENCES users(id)
);