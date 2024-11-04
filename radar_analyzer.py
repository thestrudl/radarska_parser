import requests
import shutil
from datetime import datetime
from PIL import Image
import sys
import os
import math
from geopy.geocoders import Nominatim

class RadarAnalyzer:
    RADAR_IMAGE_URL = "https://meteo.arso.gov.si/uploads/probase/www/observ/radar/si0-rm.gif"
    COLOR_SCALE = {
        19: 0.25, 18: 0.5, 17: 0.75, 16: 1, 15: 1.5, 14: 2, 13: 3.5, 12: 5,
        11: 8, 10: 15, 9: 30, 8: 50, 7: 75, 5: 100, 4: 125
    }

    def __init__(self, db_handler):
        self.db_handler = db_handler

    @staticmethod
    def safe_create_dir(directory):
        if not os.path.exists(directory):
            os.makedirs(directory)

    def download_radar_image(self):
        response = requests.get(self.RADAR_IMAGE_URL, stream=True)
        if response.status_code != 200:
            print("Failed to download radar image.")
            return None

        dir_path = "./radar_image/"
        self.safe_create_dir(dir_path)
        timestamp = datetime.now().strftime("%Y%m%d_%H:%M:%S")
        filename = os.path.join(dir_path, f"{timestamp}_radarska.gif")

        with open(filename, "wb") as f:
            shutil.copyfileobj(response.raw, f)
        return filename

    @staticmethod
    def color_to_precipitation(pixel_value):
        return RadarAnalyzer.COLOR_SCALE.get(pixel_value, 0)

    def read_pixel(self, image_path, x, y, radius):
        image = Image.open(image_path)
        pix = image.load()
        x, y = round(x), round(y)
        radius = math.ceil(radius)

        storm_flag = 0
        # Rename the inner iteration variable to avoid conflict
        sweep_area = [pix[x_inner, y_inner] for x_inner in range(x - radius, x + radius) for y_inner in range(y - radius, y + radius)]
        
        if any(4 <= storm <= 10 for storm in sweep_area):
            storm_flag = 1

        precipitation = self.color_to_precipitation(pix[x, y])
        return storm_flag, precipitation

    @staticmethod
    def get_location_data(location):
        geolocator = Nominatim(user_agent="RadarAnalyzerApp")
        location_data = geolocator.geocode(location)
        return location_data.latitude, location_data.longitude if location_data else None

    @staticmethod
    def transform_lonlat_to_xy(lat, lon, radius):
        x = lon * 152.302 - 1838.83
        y = lat * (-224.91) + 10710.4
        radiuspx = radius * 2.012
        return x, y, radiuspx

    def add_location_to_db(self, name, location, radius):
        lat, lon = self.get_location_data(location)
        x, y, radiuspx = self.transform_lonlat_to_xy(lat, lon, radius)
        self.db_handler.add_location(name, location, lat, lon, x, y, radius, radiuspx)

    def process_location(self, name):
        location_coords = self.db_handler.get_location_coordinates(name)
        if not location_coords:
            print(f"No coordinates found for location '{name}'. Exiting.")
            sys.exit(1)

        image_path = self.download_radar_image()
        if not image_path:
            sys.exit(1)

        storm_flag, precipitation = self.read_pixel(image_path, *location_coords)
        self.send_alert(storm_flag)

    @staticmethod
    def send_alert(storm_flag):
        if storm_flag:
            print(datetime.now())
            print("Storm ALERT !!!!!")
        else:
            print("No storm detected.")
