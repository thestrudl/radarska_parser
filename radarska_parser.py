import argparse
import requests
import shutil
import subprocess
from datetime import datetime
from PIL import Image
import sys
import pandas as pd
import numpy as np
import math
import csv
import os
from os.path import exists
from geopy.geocoders import Nominatim

# Link to radar image
radarska_url = "https://meteo.arso.gov.si/uploads/probase/www/observ/radar/si0-rm.gif"


def safe_create_dir(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)


def get_radarska():
    r = requests.get(radarska_url, stream=True)
    date_time = datetime.now()
    dt_string = date_time.strftime("%Y%m%d_%H:%M:%S")
    dir = "./radar_image/"
    safe_create_dir(dir)
    filename = dir + dt_string + "_radarska"

    folderchecker = subprocess.run(["bash", dir], stderr=subprocess.PIPE)
    if folderchecker.returncode:
        if b"No such file or directory" in folderchecker.stderr:
            print(
                "Directory is wrong or missing, check if filepath is correct, currently set directory is: "
                + dir
            )
            sys.exit(1)

    if r.status_code == 200:
        r.raw.decode_content = True
        with open(filename, "wb") as f:
            shutil.copyfileobj(r.raw, f)
        return filename
    else:
        print("Something went wrong with downloading the picture")


def read_pixel(image_to_analyze, x, y, radius):
    im = Image.open(image_to_analyze)
    pix = im.load()
    storm_flag = 0
    sweep_area_array = []
    x = round(x)
    y = round(y)
    radius = math.ceil(radius)
    for x in range(x - radius, x + radius):
        for y in range(y - radius, y + radius):
            sweep_area_array.append(pix[x, y])

    # This if defines the sensitivity of storm alert (color range)
    if any(storm in range(4, 11) for storm in sweep_area_array):
        storm_flag = 1
    else:
        storm_flag = 0
    return storm_flag


def send_alert(storm_flag):
    if storm_flag == 1:
        print(datetime.now())
        print("Storm ALERT !!!!!")
    else:
        print("No storm")


def get_location_coordinates(name):
    locations_df = pd.read_csv("./locations.csv")
    # Find the indices where the name matches
    indices = np.where(locations_df["name"] == name)[0]

    if len(indices) > 0:  # Check if there are any matching indices
        index = indices[0]
        x = locations_df.iloc[index, 4]
        y = locations_df.iloc[index, 5]
        radius = locations_df.iloc[index, 7]
        return x, y, radius
    else:
        print("No location with that name found")
        return None  # Return None or any other appropriate value


# New location handling and CSV writing functions
def get_locationdata(location):
    geolocator = Nominatim(user_agent="MyApp")
    location = geolocator.geocode(location)
    lat = location.latitude
    lon = location.longitude
    return (lat, lon)


def transform_lonlat_to_xy(lat, lon, radius):
    x = lon * 152.302 - 1838.83
    y = lat * (-224.91) + 10710.4
    radiuspx = radius * 2.012
    return (x, y, radiuspx)


def raw_data_to_csv(name, location, lat, lon, x, y, radius, radiuspx):
    filename = "locations.csv"
    header = ["name", "location", "lat", "lon", "x", "y", "radius", "radiuspx"]
    row_data = [name, location, lat, lon, x, y, radius, radiuspx]
    names_list = []

    file_locations_exists = exists("./locations.csv")
    if not file_locations_exists:
        with open(filename, "w", encoding="UTF-8", newline="") as write_obj:
            csv_writer = csv.writer(write_obj)
            csv_writer.writerow(header)
            csv_writer.writerow(row_data)
    else:
        with open(filename, "a+", newline="") as readwrite_obj:
            read_csv = csv.reader(readwrite_obj, delimiter=",")
            for row in read_csv:
                names_list.append(row[0])

            if name in names_list:
                print("That name is already used, name must be unique")
            else:
                csv_writer = csv.writer(readwrite_obj)
                csv_writer.writerow(row_data)


def main():
    parser = argparse.ArgumentParser(
        description="Parse Slovenian radar data and detect storms, allowing input of location names or manual addresses. If you have not added location yet use -n -l and -r arguments to specify where we need to check. If you location is already in csv file just specify the name and we will check location for storms.",
        epilog="Make sure locations.csv contains valid locations and radar data is accessible.",
    )
    parser.add_argument(
        "-n",
        "--name",
        type=str,
        help="Specify a location using a name from locations.csv or input a new one.",
    )
    parser.add_argument(
        "-l",
        "--location",
        type=str,
        help="Specify a new location address (optional, adds to CSV).",
    )
    parser.add_argument(
        "-r",
        "--radius",
        type=float,
        default=1.0,  # Set default value to 1 km
        help="Set radius in km from center location (default=1km).",
    )

    args = parser.parse_args()
    name = args.name
    location = args.location
    radius = args.radius

    if location and radius and name:
        (lat, lon) = get_locationdata(location)
        (x, y, radiuspx) = transform_lonlat_to_xy(lat, lon, radius)
        raw_data_to_csv(name, location, lat, lon, x, y, radius, radiuspx)
    elif name:
        x_y_radius = get_location_coordinates(name)
        if x_y_radius is None:
            print("Exiting program due to missing location coordinates.")
            sys.exit()  # Exit the program
        file_to_analyze = get_radarska()
        storm_flag = read_pixel(
            file_to_analyze, x_y_radius[0], x_y_radius[1], x_y_radius[2]
        )
        send_alert(storm_flag)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
