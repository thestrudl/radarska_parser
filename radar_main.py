import time
import argparse
from datetime import datetime
from radar_analyzer import RadarAnalyzer
from db_handler import DBHandler

class RadarApp:
    def __init__(self, db_host, db_user, db_password, db_name):
        self.db = DBHandler(host=db_host, user=db_user, password=db_password, database=db_name)
        self.analyzer = RadarAnalyzer(db_handler=self.db)

    def add_location(self, name, location, radius):
        """Add a location to the database by specifying name, location, and radius."""
        lat, lon = self.analyzer.get_location_data(location)
        x, y, radius_px = self.analyzer.transform_lonlat_to_xy(lat, lon, radius)
        self.db.add_location(name, location, lat, lon, x, y, radius, radius_px)
        print(f"Location '{name}' added successfully.")

    def select_location(self, name):
        """Retrieve location details from the database."""
        location_data = self.db.get_location_by_name(name)
        if location_data:
            print(f"Location '{name}' found.")
            return location_data
        else:
            print(f"No location found with the name '{name}'.")
            return None

    def check_and_log_precipitation(self, name):
        """Fetch precipitation data for a location and log it in the database."""
        location_data = self.select_location(name)
        if not location_data:
            return

        x, y, radius = location_data['x'], location_data['y'], location_data['radius']
        radar_image = self.analyzer.download_radar_image()

        storm_flag, precipitation = self.analyzer.read_pixel(radar_image, x, y, radius)
        self.db.append_precipitation_data(name, precipitation, datetime.now())

        if storm_flag:
            print("Storm detected at location:", name)
        else:
            print("No storm detected at location:", name)

    def run_periodic_check(self, location_name, interval_minutes=5):
        """Run the precipitation check for a location every `interval_minutes`."""
        while True:
            self.check_and_log_precipitation(location_name)
            time.sleep(interval_minutes * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Add/select locations and log precipitation data every 5 minutes."
    )
    parser.add_argument("-a", "--add", nargs=3, metavar=("NAME", "LOCATION", "RADIUS"),
                        help="Add a new location with name, location, and radius.")
    parser.add_argument("-c", "--check", type=str, metavar="NAME",
                        help="Check precipitation for a given location name.")
    parser.add_argument("-p", "--periodic", type=str, metavar="NAME",
                        help="Run periodic precipitation logging for a location every 5 minutes.")

    args = parser.parse_args()
    app = RadarApp(db_host="localhost", db_user="radar_user", db_password="radar_password", db_name="radar_db")


    if args.add:
        name, location, radius = args.add
        app.add_location(name, location, float(radius))

    elif args.check:
        app.check_and_log_precipitation(args.check)

    elif args.periodic:
        app.run_periodic_check(args.periodic)
