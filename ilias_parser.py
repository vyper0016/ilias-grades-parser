from configparser import ConfigParser
import codecs
import mechanicalsoup as ms
from bs4 import BeautifulSoup
import json
import rocket_parser as rp
import requests

class IliasParser:
    
    def __init__(self, user, password, new=True, other_creds = {}):
        self.browser = self.login(user, password)
        self.creds = {'user': user, 'password': password, **other_creds}
        if not self.browser:
            return
        if new:
            self.parse_courses()
            self.grades_db = {}
        else:
            with open('./data/courses.json', 'r') as f:
                self.courses_db = json.load(f)
            with open('./data/members.json', 'r') as f:
                self.members_db = json.load(f)
            with open('./data/grades.json', 'r') as f:
                self.grades_db = json.load(f)
        
    
    def login(self, user, password):
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
    
    def parse_courses(self):
        browser = self.browser
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
            
            members = self.parse_members(browser, c_soup)
            if members is not None:
                member_db[c_id] = members
            
            courses[c_id]['sub_links'] = self.parse_sub_links(c_soup)

        self.courses_db = courses        
        self.members_db = member_db
        self.save_db()
        
    def save_db(self):
        with open('./data/courses.json', 'w') as f:
            json.dump(self.courses_db, f, indent=4)
            
        with open('./data/members.json', 'w') as f:
            json.dump(self.members_db, f, indent=4) 
            
        with open('./data/grades.json', 'w') as f:
            json.dump(self.grades_db, f, indent=4) 
               
    def parse_members(self, course_soup):
        browser = self.browser
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
      
    def parse_sub_links(self, course_soup):
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
    
    def update_assignment_grades(self, course_id):
        self.grades_db[str(course_id)] = self.fetch_assignment_grades(course_id)
        self.save_db()
    
    def fetch_assignment_grades(self, course_id):
        course_id = str(course_id)
        if course_id == '1526617':    # Matinf 1
            for i in self.courses_db[course_id]['sub_links']:
                if i['title'].startswith('Abgabe der'):
                    url = i['url']
                    break
                
            self.browser.open(url)
            soup = BeautifulSoup(str(self.browser.page), 'html.parser')
            containers = soup.find_all('div', class_='il_VAccordionInnerContainer')
            out_list = []
            for c in containers:
                title = c.find('span', class_='ilAssignmentHeader')
                if title is None:
                    continue
                d = {}
                d['title'] = title.text
                form_groups = c.find_all('div', class_='form-group')
                for f in form_groups:
                    name = f.find('div', class_='il_InfoScreenProperty')
                    if name is None:
                        continue
                    name = name.text
                    if name not in {"Note", "Datum der letzten Abgabe", "Abgabetermin", "Abgegebene Dateien"}:
                        continue
                    val = f.find('div', class_='il_InfoScreenPropertyValue').text
                    
                    if name == "Note":
                        d['grade'] = float(val)
                    elif name == "Datum der letzten Abgabe":
                        d['deadline'] = val.strip()
                    elif name == "Abgabetermin":
                        d['deadline'] = val.strip()
                    elif name == "Abgegebene Dateien":
                        d['submitted'] = "Sie haben noch keine Datei abgegeben." not in val
                        
                        
                out_list.append(d)
        
            return out_list    
        elif course_id == '1526496':  # Progra
            soup = BeautifulSoup(requests.get('https://hsp.pages.cs.uni-duesseldorf.de//programmierung/website//html/points_overview.html').text, 'html.parser')
                       
 
def url_builder(href: str):
    return "https://ilias.hhu.de/" + href    
      
def get_id_from_url(url: str):
    return url.split('ref_id=')[1].split('&')[0]        
        
def parse_dotzen(s: str):
    if 'Dozent(en):' in s:
        s = s.split('Dozent(en):')[1]
        s = s.replace(',', '')
        return s.split(';')
  
  
  
if __name__ == "__main__":
    config = ConfigParser()
    config.read('./data/config.ini')

    user = config.get('LOGIN', 'user')
    password = config.get('LOGIN', 'password') 
    password = codecs.decode(password, 'rot_13')
    github_token = config.get('GITHUB', 'token')
    github_token = codecs.decode(github_token, 'rot_13')
    github_user = config.get('GITHUB', 'user')
    b = IliasParser(user, password, new=False, other_creds = {"github_token": github_token, "github_user": github_user})
    b.update_assignment_grades(1526496)
    
