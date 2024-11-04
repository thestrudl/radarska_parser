import mysql.connector
from mysql.connector import Error

class DBHandler:
    def __init__(self, host, user, password, database):
        try:
            self.connection = mysql.connector.connect(
                host=host,
                user=user,
                password=password,
                database=database
            )
            if self.connection.is_connected():
                print("Connected to MySQL database")
        except Error as e:
            print(f"Error connecting to database: {e}")
            self.connection = None

    def append_precipitation_data(self, name, precipitation, timestamp):
        if not self.connection:
            print("No database connection.")
            return

        try:
            cursor = self.connection.cursor()
            query = "INSERT INTO radar_precipitation (location_name, precipitation, timestamp) VALUES (%s, %s, %s)"

            # Ensure precipitation is a float and timestamp is a datetime string or object
            print(f"Location Name: {name}")
            print(f"Precipitation Value: {precipitation} (Type: {type(precipitation)})")
            print(f"Timestamp Value: {timestamp} (Type: {type(timestamp)})")

            cursor.execute(query, (name, float(precipitation), timestamp))
            self.connection.commit()
            print("Data appended to database.")
        except Error as e:
            print(f"Error appending data: {e}")
        finally:
            cursor.close()



    def get_location_by_name(self, name):
        if not self.connection:
            print("No database connection.")
            return None

        try:
            cursor = self.connection.cursor(dictionary=True)  # Use dictionary for easy access to columns
            query = "SELECT * FROM locations WHERE name = %s"
            cursor.execute(query, (name,))
            result = cursor.fetchone()
            if result:
                print(f"Location found: {result}")
            else:
                print("No location found with that name.")
            return result
        except Error as e:
            print(f"Error fetching location data: {e}")
            return None
        finally:
            cursor.close()


    def add_location(self, name, location, lat, lon, x, y, radius, radiuspx):
        if not self.connection:
            print("No database connection.")
            return

        try:
            cursor = self.connection.cursor()
            query = """
                INSERT INTO locations (name, location, lat, lon, x, y, radius, radiuspx)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE location=VALUES(location), lat=VALUES(lat), lon=VALUES(lon),
                                        x=VALUES(x), y=VALUES(y), radius=VALUES(radius), radiuspx=VALUES(radiuspx)
            """
            cursor.execute(query, (name, location, lat, lon, x, y, radius, radiuspx))
            self.connection.commit()
            print("Location data appended to database.")
        except Error as e:
            print(f"Error appending location data: {e}")
        finally:
            cursor.close()    


    def close(self):
        if self.connection and self.connection.is_connected():
            self.connection.close()
            print("Database connection closed.")


# This class assumes Database schema
'''
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
'''