# Lianjia-scraping
This repo is to present the process of web scraping for the rent data on lianjia, one of the most popular platform for information alike. The main features used include requests, pyquery, sqlite, selenium and AMap Geocoding API. The metro information in Canton/Guangzhou is also included via scraping the official website, which is useful for understanding the rent data among a metropolitan with advanced public transportation system. In the end, a small-scaled wrangling and visualization of the data via pandas and folium are presented.

## Acknowledgement
The latest rent data is scraped from [Lianjia](https://gz.lianjia.com/zufang/) on 22 May 2020, which keeps updating due to transaction reason.

#### Tips for the rent data collected
*The rent data collected via Lianjia platform represent the intentional prices of the landlords. According to the website, more than a half of the landlords accept further negotiation of the rent registered. Thus, the rent data scraped do not represent the final price of agreement.*

The latest metro station data is collected from the official website [Guangzhou Metro](http://cs.gzmtr.com/ckfw/) in May 2020, which is relatively stable in a few months.

The geocoding service used for getting the longitude and latitude data is [AMap Geocoding](https://lbs.amap.com/api/webservice/guide/api/georegeo) and [AMap POI](https://lbs.amap.com/api/webservice/guide/api/search) run by Alibaba.

#### Tips for the geocoding service
*The longitudes and latitudes returned are based on the coordinates different than the usual WGS84 (or EPSG 4326) CRS (coordinate reference system). 
Thus, for visualization purpose in folium, the coordinate returned should be converted to WGS84.*

## Disclaimer
As stated above, the rent data acquired represent only small amount of the platform with repect to a certain date. At the same time, the data do not represent the final price of agreement. If there is any severe violation of your benefit, please contact me without hesitation. The code posted is only for small-scaled test and study, please do not use for malignant purpose.

## Repo components
- Scraping the newest catelog of houses for rent and save to database
- Scraping details of the houses saved in the catalog and save to database
- Fetching the geodata (ie. longitude and latitude) of the houses (represented by the communities where the houses locate) and save to database
- Scraping the existing metro lines and stations and save to database
- Visualizing the most current rent data via folium

## Inspiration for further study of the data
1. How will the distance to the nearest metro station affect the rent asked for?
2. How will the elevator(s) influence the rent asked for? What about considering the floors of the houses at the same time?
3. What's the general trend for the rent asked for geometrically, like going from the west side to the east side of the city?
4. Can any model for predicting the approximate rent given certain conditions of the houses be created?

## Further improvement and update
Any suggestion related is welcomed, especially those help me to better develop the code and the data.

1. Due to Lianjia's data strategy, only about 3,000 newest records can be retrived at a certain time.
In order to study the rent data better, it would be useful to add more data into the pool as time goes by, under a reasonable and legal scrapying strategy. The data would be updated on an irregular basis.

2. More secondary factors contributing to the rent, like the electric products in the house, can be added to the data.

3. Economic data among the districts can be added, so as to get a better understanding of how economy factors influence the rent.

4. Bus transportation data in the city can be added, since the bus system is another important component of the public transportation.

