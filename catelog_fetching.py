from urllib.error import URLError
import sqlite3
import re
import random
import time
import requests
from pyquery import PyQuery as pq

HOST = 'https://gz.lianjia.com'
CATELOG_URL = 'https://gz.lianjia.com/zufang/'
CITY = 'guangzhou'

def DbInitialize(city=CITY):

    init_sql = '''
                DROP TABLE IF EXISTS `{city}`;
                CREATE TABLE IF NOT EXISTS `{city}` (
                `id` INTEGER PRIMARY KEY AUTOINCREMENT,
                `title` VARCHAR(40),
                `link` VARCHAR(255) NOT NULL,
                `district` VARCHAR(4) NOT NULL,
                `neighborhood` VARCHAR(10) NOT NULL,
                `area` NUMERIC NOT NULL,
                `price` INT NOT NULL,
                `unit` CHAR(16) NOT NULL,
                `status` TINYINT DEFAULT 0 NOT NULL,
                `houseid` BIGINT DEFAULT NULL)
               '''.format(city=city)

    conn = sqlite3.connect('lianjia.db')
    cur = conn.cursor()

    try:
        cur.executescript(init_sql)
        conn.commit()
    except:
        print('DB Initialization Error')
    finally:
        cur.close()
    
    return conn


def RecordInsert(cur, record, city=CITY):

    sql = '''
          INSERT INTO {city}
          (title, link, district, neighborhood, area, price, unit)
          VALUES 
          (:title, :link, :district, :neighborhood, :area, :price, :unit)
          '''.format(city=city)

    try:
        cur.execute(sql, record)
        num_suc = 1
    except:
        print('Insertion Error for title {:s}'.format(record['title']))
        num_suc = 0
    
    return num_suc

def GetHeader():

    with open('user-agents.txt', 'r') as fhand:
        agent = random.choice(fhand.read().split('\n'))
    header = {
        'User-Agent': agent,
        'Host': 'gz.lianjia.com'
    }
    return header


def GetMaxPage():

    r = requests.get(CATELOG_URL, headers=GetHeader())
    if r.status_code == 200:
        doc = pq(r.text)
        max_page = doc('.content__pg').attr('data-totalpage')
        
        try:
            max_page = int(max_page)
            print('{} pages found'.format(max_page))
        except ValueError:
            print('Invalid max_page number fetched')
        return max_page
    else:
        raise URLError('Connection status: {:s}'.format(r.status_code))


def GetPage(url):

    try:
        r = requests.get(url, headers=GetHeader(), timeout=10)
    except requests.exceptions.Timeout:
        print('Time out for {:s}'.format(url))
        with open('unsuccessful_summary_page.log', 'a+') as fhand:
            fhand.write(url)
        return None
    
    if r.status_code == 200:
        return r.text
    else:
        raise URLError('Connection status: {:d}'.format(r.status_code))

def ParsePage(html):

    doc = pq(html)
    records = doc('#content .content__list--item').items()

    for r in records:
        record = {
            'title': r.find('.content__list--item--title.twoline a').text(),
            'link': HOST + r.find('.content__list--item--title.twoline a').attr('href'),
            'district': r.find('.content__list--item--des a:nth-child(1)').text(),
            'neighborhood': r.find('.content__list--item--des a:nth-child(2)').text(),
            'area': re.search(r'\d+', r.find('.content__list--item--des').text()).group(0),
            'price': r.find('.content__list--item-price em').text(),
            'unit': re.sub(r'[-\d\s]+', '',  r.find('.content__list--item-price').text())
            }

        # 若面积和标价数据录入为一个区间，取区间均值
        if '-' in record['area']:
            record['area'] = sum([float(num) for num in record['area'].split('-')]) / 2
        if '-' in record['price']:
            record['price'] = sum([float(num) for num in record['price'].split('-')]) / 2
               
        yield record


def Main():

    conn = DbInitialize()
    cur = conn.cursor()
    n_suc, n_total = 0, 0

    for i in range(GetMaxPage()):
        url = '{catelog}pg{pagenum}rco11/'.format(catelog=CATELOG_URL, pagenum=i+1)
        print('Fetching...', url)
        html = GetPage(url)
        
        if html is None:
            continue

        for record in ParsePage(html):
            n_total += 1
            n_suc += RecordInsert(cur, record)
        conn.commit()
        time.sleep(random.uniform(1, 3))
    print('Successfully inserting {:d} records with {:d} in total'.format(n_suc, n_total))
    
    return None

if __name__ == '__main__':
    Main()
