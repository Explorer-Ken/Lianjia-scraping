import re
import time
import sqlite3
import random
from urllib.parse import urlencode
import requests
from requests.exceptions import Timeout, ConnectionError
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support import expected_conditions as EC
from mapkeys import GAODE_KEY

OFFICIAL_URL = 'http://cs.gzmtr.com/ckfw/'
MAX_TRY = 5
GAODE_API = 'https://restapi.amap.com/v3/place/text?'
CITY = 'guangzhou'

def DbInitialize(conn):
    '''
    初始化地铁站点数据库
    '''
    cur = conn.cursor()

    init_sql = '''
                DROP TABLE IF EXISTS `guangzhou-metro`;
                CREATE TABLE IF NOT EXISTS `guangzhou-metro`(
                `LineCode` TINYINT NOT NULL,
                `LineName` VARCHAR(8) NOT NULL,
                `LineColor` VARCHAR(32) NOT NULL,
                `StationCode` TINYINT NOT NULL,
                `StationName` VARCHAR(16) NOT NULL,
                `Longitude` NUMERIC DEFAULT NULL,
                `Latitude` NUMERIC DEFAULT NULL,
                PRIMARY KEY (`LineCode`, `StationCode`)
                )
                '''
    try:
        cur.executescript(init_sql)
        conn.commit()
    except Exception as err:
        print('DB Initialization Error', err.args[0])
    finally:
        cur.close()

    return None


def RecordDetailInsert(conn, station_records):
    '''
    将站点数据插入到数据库中，其中站点数据为对应于数据库结构的Iterable：
    单个站点数据应符合(Linecode, LineName, LineColor, StationCode, StationName)的数据格式
    '''
    cur = conn.cursor()

    sql = '''
          INSERT OR IGNORE INTO `guangzhou-metro` (
              Linecode, LineName, LineColor, StationCode, StationName)
          VALUES (
              ?, ?, ?, ?, ?
              )
          '''
    try:
        cur.executemany(sql, station_records)
        num_suc = cur.rowcount
        conn.commit()
    except sqlite3.OperationalError as err:
        print('Insertion Error for record:', station_records, err)
        num_suc = 0
    
    return num_suc


def ExtractColor(style_string):
    '''
    利用Regex解析各地铁线路的主题颜色
    '''
    pat = re.compile(r'rgb\(\d{1,3},\s*\d{1,3},\s*\d{1,3}\)')
    return pat.search(style_string).group()


def GetStations(driver):
    '''
    在每一次获取特定地铁线路的站点清单后，抓取各个站点的编号和名称
    '''
    line_table = driver.find_elements(By.CSS_SELECTOR, '#zoneService tbody tr')
    for i, elmt in enumerate(line_table):
        if i in range(0, 3):
            continue
        line_code, station_code = elmt.find_elements(By.TAG_NAME, 'td')[0].text.split('\n')
        station_name = elmt.find_elements(By.TAG_NAME, 'td')[1].text

        yield line_code, station_code, station_name


def GetStationsRecord(driver, botton):
    '''
    在每一次点击（更新线路后）打包并返回各个站点的信息
    '''
    line_name = botton.text
    line_color = ExtractColor(botton.get_attribute('style'))
    for line_code, station_code, station_name in GetStations(driver):
        yield (line_code, line_name, line_color, station_code, station_name)


def GetHeader():
    '''
    随机获取请求头信息
    '''
    with open('user-agents.txt', 'r') as fhand:
        agent = random.choice(fhand.read().split('\n'))
    header = {
        'User-Agent': agent,
        'Host': 'restapi.amap.com'
    }
    return header


def ParamsPackaging(address, city=CITY, key=GAODE_KEY):
    '''
    根据指定的站点信息返回向高德地图查询的URL
    '''
    query = urlencode([
        ('city', city), 
        ('key', key),
        ('keywords', address),
        ('types', 150500)
        ])
    
    url = GAODE_API + query
    
    return url


def StationGeocoding(url):
    '''
    根据完成编码的URL利用地图API提取站点的经纬度，并作相应的异常处理
    '''
    # 记录超时并返回None
    try:
        r = requests.get(url, headers=GetHeader(), timeout=10)
    except Timeout as terr:
        raise Timeout('Timeout for: {:s}'.format(url), terr.args[0])
    
    # 进行内容解析前先检查response状态
    if r.status_code != 200:
        raise ConnectionError(r.status_code)
        
    # 记录解码异常并返回None
    try: 
        result = r.json()
    except: 
        raise ValueError('JSON decoding error for {:s}'.format(url))
        
    # 进行经纬度提取前先检查结果状态
    if result['status'] == 0:
        raise ConnectionError('unsuccessful response {:s}'.format(result['info']))

    try:
        name = result['pois'][0]['name']
        longitude, latitude = result['pois'][0]['location'].split(',')
        return name, float(longitude), float(latitude)
    except:
        raise ValueError('Content error for result:', result)


def MetroGeoCode(conn):

    num_update = 0
    query = '''
            SELECT LineCode, StationCode, StationName FROM `guangzhou-metro`
            '''
    update_sql = '''
                 UPDATE `guangzhou-metro`
                 SET `Longitude` = ?, `Latitude` = ?
                 WHERE (`LineCode` = ?) & (`StationCode` = ?)
                 '''
    cur = conn.cursor()
    name_pattern = r'(\w+)(\(\w+\))?'

    for lcode, scode, station in cur.execute(query):
        print('Geocoding station...', station)
        url = ParamsPackaging('{:s}(地铁站)'.format(station))

        try:
            name, longitude, latitude = StationGeocoding(url)
            if re.match(name_pattern, name).group(1) != station:
                raise ValueError('Mismatch of station: {:s}'.format(station))
        except (ConnectionError, ValueError, Timeout) as err:
            print('Error occurs for station {:s}'.format(station))
            print(err.args[0])
            longitude, latitude = None, None
        
        conn.execute(update_sql, (longitude, latitude, lcode, scode))
        num_update += cur.rowcount
        time.sleep(random.uniform(0, 2))
    
    conn.commit()
    print('{:d} records updated.'.format(num_update))

    return None


def Main():

    conn = sqlite3.connect('lianjia.db')
    num_suc = 0
    DbInitialize(conn)

    browser = webdriver.Chrome()
    wait = WebDriverWait(browser, 10)
    browser.get(OFFICIAL_URL)

    for i in range(MAX_TRY):
        try:
            wait.until(EC.element_to_be_clickable((By.CLASS_NAME, 'current')))
        except TimeoutException:
            browser.refresh()
            if i == MAX_TRY - 1:
                browser.close() 

    lines_botton = browser.find_elements(By.CSS_SELECTOR, '#zoneHeader td a')

    for botton in lines_botton:
        botton.click()
        assert botton.get_attribute('class') == 'current'
        num_suc += RecordDetailInsert(conn, GetStationsRecord(browser, botton))
        time.sleep(2)

    print('{:d} records inserted.'.format(num_suc))
    
    # THZ线路为旅游性质，且需要单独作Geocoding的设计，暂不予以考虑
    conn.execute('DELETE FROM `guangzhou-metro` WHERE LineCode LIKE "THZ%"')
    
    MetroGeoCode(conn)  #少数站点存在地铁官方和地图API间的用字差异，利用SQL手动调整

    browser.close()
    conn.close()

    return None


if __name__ == '__main__':
    Main()
