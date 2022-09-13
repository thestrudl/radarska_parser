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

# If running from root be careful to use abosulte filepaths

# Link to radarska
radarska_url = "https://meteo.arso.gov.si/uploads/probase/www/observ/radar/si0-rm.gif"


def get_radarska():
    r = requests.get(radarska_url, stream=True)  # Requests image in link

    date_time = datetime.now()
    dt_string = date_time.strftime("%Y%m%d_%H:%M:%S")
    dir = "./radarske/"  # Set directory for saving radaska
    # Adjust file name and path HERE, to run from root you have to use absolute filepath
    filename = dir+dt_string+"_radarska"
    # Exception for wrong file path
    #################
    # Checks if there is maybe something wrong with paths
    folderchecker = subprocess.run(['bash', dir], stderr=subprocess.PIPE)
    if folderchecker.returncode:
        if b'No such file or directory' in folderchecker.stderr:
            print('Directory is wrong or missing, check if filepath is correct, currently set directory is: '+dir)
            sys.exit(1)
    #################
    if r.status_code == 200:  # If http transfer of request is succesful
        r.raw.decode_content = True
        with open(filename, 'wb') as f:
            shutil.copyfileobj(r.raw, f)  # Save file
            # Print("Imamo radarsko") #debug
        return filename  # Returns saved file
    else:
        print("Something went wrong with downloading picture")


def read_pixel(image_to_analyze, x, y, radius):
    im = Image.open(image_to_analyze)
    pix = im.load()
    # Colors from blue to violet
    # 19, 18, 17, 16, 15, 14, 13, 12, 11, 10 yellow, 9, 8, 7 red, 6, 5 ,4
    storm_flag = 0  # Storm no storm flag
    # Array to analyze if there is any critical zones for storm
    sweep_area_array = []

    # Rounding to get numbers appropriate to select pixels

    x = round(x)
    y = round(y)
    radius = math.ceil(radius)
    for x in range(x-radius, x+radius):
        for y in range(y - radius, y + radius):
            sweep_area_array.append(pix[x, y])  # Appends values of area sweeped into array for if below

    # print(sweep_area_array) #prints array for debug
    if any(storm in range(4, 11) for storm in sweep_area_array):  #in this range set sensitivity of the storm alert
        storm_flag = 1 
    else:
        storm_flag = 0
    return storm_flag

def send_alert(storm_flag):
    if storm_flag == 1:  # Do something if there is STORM
        print(datetime.now())
        print("Storm ALERT !!!!!")
    else:  # Do something if there is no storm
        print("No storm")

#put in while 1 with timer if you want script to run continously

def get_data_from_csv(name):
    locations_df = pd.read_csv("./locations.csv")
    index=np.where(locations_df["name"] == name)[0][0] #gets row index that corelates to entry in CSV in scalar/int form
    x = locations_df.iloc[index,4]
    y = locations_df.iloc[index,5]
    radius = locations_df.iloc[index,7]
    return x, y, radius

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-n","--name", type=str, help="Specify your location using name from list of locations in locations.csv", required=True)
    args = parser.parse_args()
    name = args.name

    x,y,radius = get_data_from_csv(name)

    file_to_analyze = get_radarska() #fetches latest radarska for ARSO and saves file and path

    storm_flag = read_pixel(file_to_analyze, x, y, radius) #insert image to analyze here, returns 0 (no storm), 1 (storm)

    send_alert(storm_flag) #Does something dependent on the storm flag
        

main()