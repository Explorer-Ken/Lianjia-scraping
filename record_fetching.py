from urllib.parse import urlsplit
import sqlite3
import re
import random
import time
import requests
from requests.exceptions import Timeout, ConnectionError
from pyquery import PyQuery as pq

BASE_URL = 'https://gz.lianjia.com/zufang/'
CITY = 'guangzhou'

def RecordDbInitialize(conn, city=CITY):

    cur = conn.cursor()

    init_sql = '''
               CREATE TABLE IF NOT EXISTS `{city}-detail`(
               `ID` BIGINT NOT NULL PRIMARY KEY,
               `InfoDate` INTEGER,
               `District` VARCHAR(4) NOT NULL,
               `Neighborhood` VARCHAR(8) NOT NULL,
               `Community` VARCHAR(16) NOT NULL,
               `RentType` VARCHAR(4),
               `Condition` VARCHAR(8),
               `Area` NUMERIC NOT NULL,
               `Price` INT NOT NULL,
               `Unit` VARCHAR(8) NOT NULL,
               `HouseFloor` CHAR(4),
               `BuldFloor` TINYINT,
               `ElevatorFlag` CHAR(2)
               )
               '''.format(city=city)

    try:
        cur.execute(init_sql)
        conn.commit()
    except:
        print('DB Initialization Error')
    finally:
        cur.close()
    
    return conn


def RecordDetailInsert(conn, detail, city=CITY):

    cur = conn.cursor()

    sql = '''
          INSERT OR IGNORE INTO `{city}-detail` (
              ID, InfoDate, District, Neighborhood, Community, RentType, Condition,
              Area, Price, Unit, HouseFloor, BuldFloor, ElevatorFlag)
          VALUES (
              :HouseID, :InfoDate, :District, :Neighborhood, :Community, :RentType,
              :Condition, :Area, :Price, :Unit, :HouseFloor, :BuldFloor, :ElevatorFlag)       
          '''.format(city=city)

    try:
        cur.execute(sql, detail)
        num_suc = cur.rowcount
    except sqlite3.OperationalError as err:
        print('Insertion Error for ID {:d}:'.format(detail['HouseID']), err)
        num_suc = 0
    
    return num_suc

def StatusUpdate(conn, rid, sid, city=CITY):

    cur = conn.cursor()
    try:
        cur.execute(
            'UPDATE `{city}` SET status = 1, houseid = ? WHERE id = ?'.format(city=city), (rid, sid)
            )
    except sqlite3.OperationalError as err:
        print('Update Error for ID {:d}:'.format(sid), err)

    cur.close()
    return None


def InvalidDelete(conn, sid, city=CITY):

    cur = conn.cursor()
    try:
        cur.execute('DELETE FROM `{city}` WHERE id = ?'.format(city=city), (sid, ))
    except sqlite3.OperationalError as err:
        print('Delete Error for ID {:d}:'.format(sid), err)

    cur.close()
    return None


def GetHeader():

    with open('user-agents.txt', 'r') as fhand:
        agent = random.choice(fhand.read().split('\n'))
    header = {
        'User-Agent': agent,
        'Host': 'gz.lianjia.com'
    }
    return header


def GetPage(url):
    
    try:
        r = requests.get(url, headers=GetHeader(), timeout=10)
    except Timeout as terr:
        print('Timeout for {:s}'.format(url), terr)

        with open('unsuccessful_detail_page.log', 'a+') as fhand:
            fhand.write('Timeout for:\n')
            fhand.write(url)
            fhand.write('\n')

        return None

    if r.status_code == 200:
        return r.text
    else:
        print('Connection error {:d} for: {:s}'.format(r.status_code, url))

        with open('unsuccessful_detail_page.log', 'a+') as fhand:
            fhand.write('Connection error {:d}:\n'.format(r.status_code))
            fhand.write(url)
            fhand.write('\n')

        return None


def GetDetail(conn, city=CITY):

    num_total, num_suc = 0, 0

    cur = conn.cursor()
    cur.execute('SELECT * FROM `{city}`'.format(city=city))
    # (id, title, link, district, neighborhood, area, price, unit, status, houseid)

    for rec in cur:
        
        # 跳过已经处理过的summary数据
        if rec[-2] == 1:
            print('Skipping repeated record...{:s}'.format(rec[1]))
            continue
        
        print('Retriving record {:d}...{:s}'.format(rec[0], rec[1]))
        num_total += 1
        
        try:
            detail = GetOneDetail(rec[1:-2])
            print(detail)
        except ValueError as verr:  # 剔除非广州范围及第三方上传的租房信息
            print('Invalid record {:d}...{:s}: {}'.format(rec[0], rec[1], verr.args[0]))
            InvalidDelete(conn, sid=rec[0])
            continue
        except ConnectionError as cerr:  # 跳过链接无效、超时的租房信息
            print('Connection failed for {:d}...{:s}：{}'.format(rec[0], rec[1], cerr.args[0]))
            continue

        # 对已经下架的summary数据不作插入，但同样更新为已处理
        num_suc += RecordDetailInsert(conn, detail)
        StatusUpdate(conn, rid=detail['HouseID'], sid=rec[0])

        if num_total % 20 == 0:  # 每处理完成20条summary记录做一次commit
            conn.commit()

        time.sleep(max(0, random.gauss(2, 0.5)))

    conn.commit()

    print('Retrive {:d} detail records with {:d} succeeded'.format(num_total, num_suc))

    return None


def GetOneDetail(rec):
    
    title, link, district, neighborhood, area, price, unit = rec

    title = re.sub(r'[^\u00b7\w\s]', '', title)
    renttype, community, condition = re.search(r'(.+)?·([\w]+)\s(.*)\s?.*', title).groups()
    
    info = {'District': district, 'Neighborhood': neighborhood, 'Community': community, \
    'RentType': renttype, 'Condition': condition, 'Area': area, 'Price': price, 'Unit': unit}

    add_info = ParseDetailPage(link)
    info.update(add_info)

    return info


def ParseDetailPage(link):

    #with open('temp.html', 'r+') as fhand:
    #    html = fhand.read()
    # 删除信息质量较差的公寓数据
    if not urlsplit(link)[2].startswith('/zufang/'):
        raise ValueError('The house is provided by third-party and to be deleted.')
    
    html = GetPage(link)

    if html is None:
        raise ConnectionError('Unable to fetch additional detail.')

    detail = pq(html)
    
    if detail('.offline'): # 对已下架的房源信息返回空值
        return {'HouseID': None, 'InfoDate': None, 'HouseFloor': None, \
    'BuldFloor': None, 'ElevatorFlag': None}
    
    houseID_raw = detail('.house_code').text()
    infodate_raw = detail('.content__subtitle').text()
    floor_raw = detail('#info > ul:nth-child(2) > li:nth-child(8)').text()
    elevator_flag = re.split(r'[:：]', detail('#info > ul:nth-child(2) > li:nth-child(9)').text())[1]
    
    city, houseID = re.search(r'(?P<city>[A-Z]+)(?P<id>\d+)', houseID_raw).groups()

    if city != 'GZ':
        raise ValueError('The house is not in Guangzhou.')

    infodate = re.search(r'\d{4}-\d{2}-\d{2}', infodate_raw).group()
    housefloor, buldfloor = re.search(r'.*：(?P<housefloor>.+)/(?P<buldfloor>\d+).*', floor_raw).groups()

    return {'HouseID': houseID, 'InfoDate': infodate, 'HouseFloor': housefloor, \
    'BuldFloor': buldfloor, 'ElevatorFlag': elevator_flag}


def Main():
    
    with sqlite3.connect('lianjia.db') as conn:
        RecordDbInitialize(conn)
        GetDetail(conn)
    
    return None


if __name__ == '__main__':
    Main()
