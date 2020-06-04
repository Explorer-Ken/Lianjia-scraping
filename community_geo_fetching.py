from urllib.parse import urlencode
import random
import sqlite3
import time
import requests
from requests.exceptions import Timeout, ConnectionError
from mapkeys import GAODE_KEY

GAODE_API = 'https://restapi.amap.com/v3/geocode/geo?'
CITY = 'guangzhou'

def CommunityDbInitialize(conn, city=CITY):

    cur = conn.cursor()

    init_sql = '''
               CREATE TABLE IF NOT EXISTS `{city}-community`(
               `ID` INTEGER PRIMARY KEY AUTOINCREMENT,
               `District` VARCHAR(4) NOT NULL,
               `Community` VARCHAR(16) NOT NULL UNIQUE,
               `Longitude` NUMERIC DEFAULT NULL,
               `Latitude` NUMERIC DEFAULT NULL
               )
               '''.format(city=city)
    
    try:
        cur.execute(init_sql)
        conn.commit()
    except sqlite3.OperationalError as err:
        print('DB Initialization Error', err.args[0])
    finally:
        cur.close()
    
    return None

def CommunityGeoInsert(conn, georecord, city=CITY):

    cur = conn.cursor()
    sql = '''
          INSERT OR IGNORE INTO `{city}-community`(
              District, Community, Longitude, Latitude)
          VALUES(
              :District, :Community, :Longitude, :Latitude
          )
          '''.format(city=city)

    try:
        cur.execute(sql, georecord)
        num_suc = cur.rowcount
    except sqlite3.OperationalError as err:
        print('Insertion Error for Community {:s}:'.format(georecord['Community']), err)
        num_suc = 0
    finally:
        cur.close()
    
    return num_suc


def ParamsPackaging(district, community, city=CITY, key=GAODE_KEY):
    '''
    打包查询参数
    '''
    query = urlencode([
        ('city', city), 
        ('key', key),
        ('address', ' '.join([district, community]))
        ], doseq=True)
    
    url = GAODE_API + query
    
    return url

def GetHeader():

    with open('user-agents.txt', 'r') as fhand:
        agent = random.choice(fhand.read().split('\n'))
    header = {
        'User-Agent': agent,
        'Host': 'restapi.amap.com'
    }
    return header

def CommunityGeocoding(url):
    '''
    根据完成编码的URL利用地图API提取小区的经纬度，并作相应的异常处理
    '''
    # 记录超时并返回None
    try:
        r = requests.get(url, headers=GetHeader(), timeout=10)
    except Timeout as terr:
        print('Timeout for: {:s}'.format(url), terr.args[0])  

        with open('unsuccessful_geo_fetching.log', 'a+') as fhand:
            fhand.write('Timeout:\n')
            fhand.write(url)
            fhand.write('\n')

        return None
    
    # 进行内容解析前先检查response状态
    if r.status_code != 200:
        raise ConnectionError('Connection response:', r.status_code)
        
    # 记录解码异常并返回None
    try: 
        result = r.json()
    except: 
        print('JSON decoding error for {:s}'.format(url))

        with open('unsuccessful_geo_fetching.log', 'a+') as fhand:
            fhand.write('JSON decoding error for:\n')
            fhand.write(url)
            fhand.write('\n')

        return None
        
    # 进行经纬度提取前先检查结果状态
    if result['status'] == 0:
        raise ConnectionError('Unsuccessful response {:s}'.format(result['info']))

    try:
        longitude, latitude = result['geocodes'][0]['location'].split(',')
        return float(longitude), float(latitude)
    except:
        print('Content error for {:s}'.format(url))

        with open('unsuccessful_geo_fetching.log', 'a+') as fhand:
            fhand.write('Content error for:\n')
            fhand.write(url)
            fhand.write('\n')

        return None


def GetGeoRecord(district, community):
    '''
    将提取的小区信息转化为数据库数据：(ID, 行政区, 小区, 经度, 纬度, 数据状态)
    '''
    url = ParamsPackaging(district, community)

    try:
        longitude, latitude = CommunityGeocoding(url)

    except ConnectionError as cerr:
        longitude, latitude = None, None

        print('Connection error:', cerr.args[0])
        with open('unsuccessful_geo_fetching.log', 'a+') as fhand:
            fhand.write('Connection error:', cerr.args[0], '\n')
            fhand.write(url)
            fhand.write('\n')

    except TypeError:
        longitude, latitude = None, None
        
    return {'District': district, 'Community': community,
    'Longitude': longitude, 'Latitude': latitude}


def Main(city=CITY):

    num_suc, num_total = 0, 0
    conn = sqlite3.connect('lianjia.db')
    CommunityDbInitialize(conn)

    cur = conn.cursor()
    extract_sql = 'SELECT DISTINCT District, Community FROM `{city}-detail`'.format(city=city)
    check_sql = '''SELECT Longitude, Latitude FROM `{city}-community`
                   WHERE (District=?) AND (Community=?)
                '''.format(city=city)

    for rec in cur.execute(extract_sql):
        num_total += 1
        check_result = conn.execute(check_sql, rec).fetchone()
        
        if check_result and (None not in check_result):
            continue

        community_georecord = GetGeoRecord(*rec)
        num_suc += CommunityGeoInsert(conn, community_georecord)
        time.sleep(random.uniform(0, 2))

        if num_total % 20 == 0:
            conn.commit()
            print('Inserting {:d} geocoding records with {:d} succeeded'.format(num_total, num_suc))
    
    conn.commit()
    print('Inserting {:d} geocoding records with {:d} succeeded'.format(num_total, num_suc))

    cur.close()
    conn.close()

    return None

if __name__ == '__main__':
    Main()
