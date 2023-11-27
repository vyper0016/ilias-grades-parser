from configparser import ConfigParser
import codecs
import mechanicalsoup as ms
from bs4 import BeautifulSoup
import json
import rocket_parser as rp

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
    member_db = {}
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
        
        members = parse_members(browser, c_soup)
        if members is not None:
            member_db[c_id] = members
        
        courses[c_id]['sub_links'] = parse_sub_links(c_soup)
    
    with open('./data/courses.json', 'w') as f:
        json.dump(courses, f, indent=4)

    with open('./data/members.json', 'w') as f:
        json.dump(member_db, f, indent=4)
        
def get_id_from_url(url: str):
    return url.split('ref_id=')[1].split('&')[0]        
        
def parse_dotzen(s: str):
    if 'Dozent(en):' in s:
        s = s.split('Dozent(en):')[1]
        s = s.replace(',', '')
        return s.split(';')

def parse_members(browser, course_soup):
    tab_members = course_soup.find('li', id='tab_members')
    if tab_members is None:
        return
    url = tab_members.find('a').get('href')
    browser.open(url_builder(url))
    members_soup = BeautifulSoup(str(browser.page), 'html.parser')
    members = members_soup.find('div', class_='il-deck')
    members = members.find_all('div', class_='il-card')
    out = {'total': len(members), 'members': []}
    
    for m in members:
        m_dict = {'username': m.find('dl').find('dd').text}
        
        title = m.find('div', class_='card-title')
        name = title.find('a')
        if name:
            m_dict['name'] = name.text
            out['members'].append(m_dict)
            continue
        
        name = rp.get_name_by_username(m_dict['username'])
        if name:
            m_dict['name'] = name
            out['members'].append(m_dict)        
    
    out['total_named'] = len(out['members'])
    return out


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
        
if __name__ == "__main__":
    b = login()
    parse_courses(b)
