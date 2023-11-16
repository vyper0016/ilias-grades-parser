from configparser import ConfigParser
import codecs
import mechanicalsoup as ms
from bs4 import BeautifulSoup
from shortuuid import uuid
import json

config = ConfigParser()
config.read('./data/config.ini')

user = config.get('LOGIN', 'user')
password = config.get('LOGIN', 'password') 
password = codecs.decode(password, 'rot_13')

def login():
    browser = ms.StatefulBrowser()

    browser.open("https://ilias.hhu.de/login.php?client_id=UniRZ&cmd=force_login&lang=de")

    browser.select_form('form[id="form_"]')
    browser["username"] = user
    browser["password"] = password
    browser.submit_selected()

    current_url = browser.get_url()
    if "ilDashboardGUI" in current_url:
        print("Login successful")
        return browser
    
    print("Login failed")

def url_builder(href: str):
    return "https://ilias.hhu.de/" + href    
    
def parse_courses(browser):
    soup = BeautifulSoup(str(browser.page), 'html.parser')
    courses = {}
    course_bodies = soup.find_all('div', class_='media-body')
    for c in course_bodies:
        d = c.find('div', class_='il-item-title')
        if d is None:
            continue
        c_url = d.find('a').get('href')
        c_id = get_id_from_url(c_url)
        if c_id in courses:
            continue
        courses[c_id] = {
            'title': d.find('a').text,
            'url': c_url,
        }
        d = c.find('div', class_='il-item-description')
        dotz = parse_dotzen(d.text)
        if dotz is not None:
            courses[c_id]['profs'] = dotz
        
        browser.open(url_builder(courses[c_id]['url']))
        c_soup = BeautifulSoup(str(browser.page), 'html.parser')
        
        members = count_members(browser, c_soup)
        if members is not None:
            courses[c_id]['members'] = members
        
        courses[c_id]['sub_links'] = parse_sub_links(c_soup)
    
    with open('./data/courses.json', 'w') as f:
        json.dump(courses, f, indent=4)

def get_id_from_url(url: str):
    return url.split('ref_id=')[1].split('&')[0]        
        
def parse_dotzen(s: str):
    if 'Dozent(en):' in s:
        s = s.split('Dozent(en):')[1]
        s = s.replace(',', '')
        return s.split(';')

def count_members(browser, course_soup):
    tab_members = course_soup.find('li', id='tab_members')
    if tab_members is None:
        return
    url = tab_members.find('a').get('href')
    browser.open(url_builder(url))
    members_soup = BeautifulSoup(str(browser.page), 'html.parser')
    members = members_soup.find('div', class_='il-deck')
    members = members.find_all('div', class_='il-card')
    return len(members)

def parse_sub_links(course_soup):
    containers = course_soup.find_all('div', class_='ilContainerListItemOuter')
    sub_links = []
    for c in containers:
        item = {}
        container_title = c.find('div', class_='il_ContainerItemTitle')
        if container_title is None:
            continue
        try:
            item['title'] = container_title.find('a').text
            item['url'] = url_builder(container_title.find('a').get('href'))
        except AttributeError:
            item['title'] = container_title.text
            
        try:
            item['icon'] = url_builder(c.find('div', class_='ilContainerListItemIcon').find('img').get('src'))
        except AttributeError:
            pass
        try:
            item['description'] = c.find('div', class_='il_Description').text
        except AttributeError:
            pass
        sub_links.append(item)
    return sub_links
        
b = login()
parse_courses(b)
