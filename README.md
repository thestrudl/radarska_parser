# Slovenian Radar Data Storm Detector

This Python script parses Slovenian radar data and detects storms based on specified locations. Users can input location names or addresses, and if the location is not already in the system, it can be added for future use.

## Features

- Download radar images for storm detection.
- Check for storms based on pixel values in the radar image.
- Store and manage locations in a CSV file.
- Geocode new location addresses to get their coordinates.
- Flexible radius setting for storm detection.

## Requirements

- Python 3.x
- Required packages:
  - `argparse`
  - `requests`
  - `Pillow`
  - `pandas`
  - `numpy`
  - `geopy`

You can install the required packages using pip:

```bash
pip install requests Pillow pandas numpy geopy
```
## Usage
```bash
python radarska_parser.py -n <location_name> -l <location_address> -r <radius>
```
```bash
python script.py -n "Existing Location Name"
```

```bash
python script.py -n "New Location Name" -l "123 Main St, Ljubljana, Slovenia" -r 5
```
