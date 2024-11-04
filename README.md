# Slovenian Radar Data Storm Detector

This Python script parses Slovenian radar data and detects storms based on specified locations. Users can input location names or addresses, and if the location is not already in the system, it can be added for future use.

## Features

- Download radar images for storm detection.
- Check for storms based on pixel values in the radar image.
- Store and manage locations in mysql database
- Geocode new location addresses to get their coordinates.
- Flexible radius setting for storm detection.
- Log historic precipitation data of certain location

## Requirements

- Python 3.x
- Required packages:
  - `argparse`
  - `requests`
  - `Pillow`
  - `pandas`
  - `numpy`
  - `geopy`
  - 

You can install the required packages using pip:

```bash
pip3 install -r requirements.txt
```
## Usage

Run the script using the following command:

```bash
./bin/python3 radar_main.py [-h] [-a NAME LOCATION RADIUS] [-c NAME] [-p NAME]
```

## Options

  - -h, --help Show this help message and exit.
  - -a, --add NAME LOCATION RADIUS Add a new location with the specified name, location, and radius.
  - -c, --check NAME Check precipitation for a given location name.
  - -p, --periodic NAME Run periodic precipitation logging for a location every 5 minutes.

## MySQL Database Setup

To use this project, you need to create the necessary database tables in MySQL. Below are the SQL commands to create the required tables.

```mysql
CREATE TABLE locations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    location VARCHAR(100),
    lat FLOAT,
    lon FLOAT,
    x FLOAT,
    y FLOAT,
    radius FLOAT,
    radiuspx FLOAT
);

CREATE TABLE radar_precipitation (
    id INT AUTO_INCREMENT PRIMARY KEY,
    location_name VARCHAR(50),
    precipitation FLOAT,
    timestamp DATETIME,
    FOREIGN KEY (location_name) REFERENCES locations(name)
);
```
 Note: Make sure to edit the database credentials in radar_main.py - main of radar_main.py:
 Locate the RadarApp class instantiation in radar_main.py and update
 the following parameters with your MySQL database information:

 db_host="localhost"        # Database host
 db_user="radar_user"       # Database username
 db_password="radar_password"  # Database password
 db_name="radar_db"         # Database name
