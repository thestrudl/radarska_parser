from geopy.geocoders import Nominatim
import argparse 
import csv
from os.path import exists


def get_locationdata(location):
    geolocator = Nominatim(user_agent="MyApp")

    location = geolocator.geocode(location)
    lat = location.latitude
    lon = location.longitude
    return (lat, lon)


def transform_lonlat_to_xy(lat, lon, radius):#specific to image provided by ARSO
    #13.714987*k+n=250, 16.610542*k+n=691
    #46.8691748*k+n=169, 44.7927906*k+n=636
    #tramsform lon to X
    #k=152.302
    #n=-1838.83
    x = lon*152.302-1838.83
    #transform lat to Y
    #k=-224.91
    #n=10710.4
    y = lat*(-224.91)+10710.4

    #transformation for distance (Measured using GMaps between Murska Sobota and Jesenice)
    #327.15 px of distance to 162.62km 2,012px to km
    radiuspx = radius*2.012
    return (x, y, radiuspx)

def raw_data_to_csv(name, location, lat, lon, x, y, radius, radiuspx):

    filename = "locations.csv"

    header = ["name","location","lat","lon","x","y","radius","radiuspx"]
    row_data = [name,location,lat,lon,x,y,radius,radiuspx]
    names_list = []



    file_locations_exists = exists("./locations.csv") #checks if CSV locations.csv already exists
    if file_locations_exists == False: #creates new file
        with open(filename,"w",encoding="UTF-8", newline='') as write_obj:
            csv_writer = csv.writer(write_obj)
            csv_writer.writerow(header)
            csv_writer.writerow(row_data)
    else: #appends to existing locations.csv file
        with open(filename, 'a+', newline='') as readwrite_obj:
            read_csv = csv.reader(readwrite_obj, delimiter=',')
            for row in read_csv:
                print(row)
                names_list.append(row[0])
                print(row[0])
            
            if any(x==name for x in names_list):
                print("That name is already used, name must be unique")
            else:
                csv_writer = csv.writer(readwrite_obj)
                csv_writer.writerow(row_data)



def main():
    #parsing arguments with argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("-n","--name", type=str, help="Name your location.", required=True)
    parser.add_argument("-l","--location", type=str, help="Input location address you want to get parameters for.", required=True)
    parser.add_argument("-r","--radius", help="Enter how big radius do you want from your centre location in km (Default=1km)", default=1, type=float)
    args = parser.parse_args()
    #saving input arguments
    name = args.name
    location = args.location
    radius = args.radius #in km

    

    (lat, lon) = get_locationdata(location)
    (x,y, radiuspx) = transform_lonlat_to_xy(lat, lon, radius)
    
    raw_data_to_csv(name, location, lat, lon, x, y, radius, radiuspx)

main()