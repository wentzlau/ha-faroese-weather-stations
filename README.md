# ha-faroese-weather-stations
Integration for Home Assistant that fetches weather information from faroese weather stations.
At the moment it fetches weather data from weather stations managed by [Landsverk](https://lv.fo) 
## Installation
### Via HACKS
Add this repository to HACKS via HACKS/user defined repositories
### Manual installation
1) Create a subfolder called fo_weather_stations in the .homeassistant/custom_components folder. 
2) Copy the contents of the ha-faroese-weather-stations/custom_components/fo_weather_stations folder into the newly created subfolder.

## Configuration
Add the the sensor section below to configuration.yaml.
Under the stations section enter one or more weather stations to integrate into Home Assistant.
A set of sensors are created for each weather station.
```
sensor:    
  - platform: fo_weather_stations    
    stations:    
      - lv_krambatangi    
      - lv_hvalba
```
  The following stations are available:
* lv_kambsdalur, Kambsdalur
* lv_hogareyn, Høgareyn
* lv_sund, Sund
* lv_runavik, Runavík
* lv_vatnsoyrar, Vatnsoyrar
* lv_klaksvik, Klaksvík
* lv_sandoy, Sandoy, á Brekkuni Stóru
* lv_sydradalur, Syðradalur
* lv_porkerishalsur, Porkerishálsur
* lv_krambatangi, Krambatangi
* lv_skopun, Skopun
* lv_nordradalsskard, Norðradalsskarð
* lv_tjornuvík, Tjørnuvík
* lv_nordurisundum, Norðuri í Sundum, Kollaf
* lv_nordskalatunnilin, Norðskálatunnilin
* lv_kaldbaksbotnur, Kaldbaksbotnur
* lv_gotueidi, Gøtueiði
* lv_dalavegur, Dalavegur til Viðareiðis
* lv_sandavagshalsi, Á Sandavágshálsi
* lv_gjaarskard, Gjáarskarð
* lv_heltnin, Heltnin, Oyndarfjarðarvegurin
* lv_hvalba, Hvalba
* lv_streymnes, Streymnes
* lv_velbastadhals, Við Velbastaðháls
* lv_ordaskard, Ørðaskarð
