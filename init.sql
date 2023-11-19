CREATE DATABASE IF NOT EXISTS mydb;
USE mydb;

CREATE TABLE IF NOT EXISTS clients (
    tax_id VARCHAR(255) NOT NULL PRIMARY KEY,
    company VARCHAR(255) NOT NULL,
    city VARCHAR(255) NOT NULL,
    postal_code VARCHAR(255) NOT NULL,
    address VARCHAR(255) NOT NULL,
    phone INT NOT NULL,
    email VARCHAR(255) NOT NULL
);

CREATE TABLE IF NOT EXISTS statuses (
    id INT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(255),
    date DATE
);

CREATE TABLE IF NOT EXISTS printers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    serial_number VARCHAR(255) NOT NULL,
    black_counter INT NOT NULL,
    color_counter INT NOT NULL,
    tax_id VARCHAR(255),
    statuses_id INT,
    FOREIGN KEY (tax_id) REFERENCES clients(tax_id),
    FOREIGN KEY (statuses_id) REFERENCES statuses(id)
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
    email VARCHAR(255),
    name VARCHAR(255) NOT NULL
);