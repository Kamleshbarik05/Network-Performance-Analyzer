
# This file checks internet download and upload speed

import speedtest

def check_speed():

    print("\nChecking Internet Speed...")

    st = speedtest.Speedtest()

    download_speed = st.download() / 10**6
    upload_speed = st.upload() / 10**6

    print("Download Speed:", round(download_speed,2), "Mbps")
    print("Upload Speed:", round(upload_speed,2), "Mbps")