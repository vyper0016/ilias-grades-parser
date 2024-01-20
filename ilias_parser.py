from configparser import ConfigParser
import codecs
import mechanicalsoup as ms
from bs4 import BeautifulSoup
import json
import rocket_parser as rp
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import threading

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
        
    def update_sub_links(self, course_id):
        self.browser.open(url_builder(self.courses_db[str(course_id)]['url']))
        self.courses_db[str(course_id)]['sub_links'] = self.parse_sub_links(BeautifulSoup(str(self.browser.page), 'html.parser'))
        self.save_db()
    
    def fetch_assignment_grades(self, course_id):
        course_id = str(course_id)
        print("Fetching grades for course", self.courses_db[course_id]['title'])
        grades = []
        grades_sum = 0
        grades_max = 0
        if course_id == '1526617':    # Matinf 1
            self.update_sub_links(course_id)
            for i in self.courses_db[course_id]['sub_links']:
                if i['title'].startswith('Abgabe der'):
                    url = i['url']
                    break
                
            self.browser.open(url)
            soup = BeautifulSoup(str(self.browser.page), 'html.parser')
            containers = soup.find_all('div', class_='il_VAccordionInnerContainer')
            for c in containers:
                title = c.find('span', class_='ilAssignmentHeader')
                if title is None:
                    continue
                d = {}
                d['title'] = title.text.replace(' (Verpflichtend)', '')
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
                
                try:
                    grades_sum += d['grade']                      
                except KeyError:
                    pass
                d['max_grade'] = 20
                grades.append(d)
                grades_max += 20
        
        elif course_id == '1526496':  # Progra
            
            firefox_options = webdriver.FirefoxOptions()
            firefox_options.add_argument("--headless")
            
            driver = webdriver.Firefox(options=firefox_options)
            
            driver.get('https://hsp.pages.cs.uni-duesseldorf.de//programmierung/website//html/points_overview.html')
            driver.find_element(By.ID, 'github_token').send_keys(self.creds['github_token'])
            driver.find_element(By.ID, 'github_name').send_keys(self.creds['github_user'])
            driver.find_element(By.CSS_SELECTOR, 'button[onclick="fetchPoints()"]').click()
            driver.implicitly_wait(0.3)
            WebDriverWait(driver, 10).until(EC.text_to_be_present_in_element((By.ID, 'messagesystem'), '/'))
            WebDriverWait(driver, 10).until(EC.text_to_be_present_in_element((By.ID, 'chess'), '/'))
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            driver.close()
            sheets = soup.find_all('tr', class_='sheet')
            for s in sheets:
                
                sheet_dic = {'title': s.find('td', class_='sheetname').text, 'max_grade': 0}
                total = s.find('td', class_='total')
                if total.text:
                    sheet_dic['grade'] = int(total.text)
                    grades_sum += sheet_dic['grade']
                
                for b in s.find_all('td'):  
                    a = b.find('a')
                    if a is None:
                        continue
                    grades_max += int(a.text.split('/')[1])
                    sheet_dic['max_grade'] += int(a.text.split('/')[1])
                grades.append(sheet_dic)
        
        elif course_id == '1526715':  # Rechnerarchitektur            
            self.update_sub_links(course_id)

            urls = [i['url'] for i in self.courses_db[course_id]['sub_links'] if i['title'].startswith('Übungsblatt')]
            grades, grades_sum, grades_max = self.grades_template1(urls)

        elif course_id == '1526712': # WA
            for i in self.courses_db[course_id]['sub_links']:
                if i['title'].startswith('Übung'):
                    url = i['url']
                    break
            self.browser.open(url)
            soup = BeautifulSoup(str(self.browser.page), 'html.parser')
            hs = soup.find_all('h3', class_='il_ContainerItemTitle')
            urls = []
            for h in hs:
                a = h.find('a')
                if a is None:
                    continue
                if not a.text.startswith('Test'):
                    continue
                urls.append(a['href'])
            grades, grades_sum, grades_max = self.grades_template1(urls)                
                
        t = {'title': self.courses_db[course_id]['title'] ,'grades': grades, 'percentage_total': grades_sum/grades_max}
        t['zugelassen'], t['percentage_zulassung'] = self.zulassung(course_id, grades)
        print("Done fetching grades for course", t['title'])
        return t
        
    def zulassung(self, course_id, grades):
        if course_id == '1526715': # Rechnerarchitektur
            return self.zulassung_helper_2parts(grades, (3, 9), (9, 15), 135, 135, 300)
        
        if course_id == '1526617': # Matinf 1
            return self.zulassung_helper(grades, (1, 14), sum_min=130)
        
        if course_id == '1526496': # Progra
            return self.zulassung_helper_2parts(grades, (3, 9), (9, 14), 60, 60, 140)
        
        if course_id == '1526712': # WA
            return self.zulassung_helper(grades, (1, 11), percentage_min=0.5)
        
    def zulassung_helper_2parts(self, grades, sum1_tuple: tuple[2], sum2_tuple: tuple[2], sum1_min: float, sum2_min: float, sum_total_min: float):        
        sum1 = 0
        sum2 = 0
        range1 = [str(i) for i in range(*sum1_tuple)]
        range2 = [str(i) for i in range(*sum2_tuple)]
        
        for g in grades:
            if 'grade' not in g:
                continue
            title = g['title'].split(' ')[-1]
            
            if title in range1:
                sum1 += g['grade']
            elif title in range2:
                sum2 += g['grade']
                
        return sum1 >= sum1_min and sum2 >= sum2_min and (sum1 + sum2) >= sum_total_min, (sum1 + sum2) / sum_total_min
    
    def zulassung_helper(self, grades, sum_tuple: tuple[2], sum_min: float = None, percentage_min: float = None):
        sum = 0
        if sum_min is None:
            assert percentage_min is not None, "Either sum_min or percentage_min must be specified"
            assert 'max_grade' in grades[0], "Cannot calculate percentage without max_grade"
            sum_max = 0
        else:
            assert percentage_min is None, "Either sum_min or percentage_min must be specified"
                
        for g in grades:
            if g['title'].split(' ')[-1] in [str(i) for i in range(*sum_tuple)]:
                try:
                    sum += g['grade']
                except KeyError:
                    continue
                
                if percentage_min is not None:
                    sum_max += g['max_grade']
                
        if percentage_min is not None:
            return sum / sum_max >= percentage_min, (sum / sum_max)  / percentage_min
              
        return sum >= sum_min, sum/sum_min
        
    def grades_template1(self, urls):
        grades = []
        grades_sum = 0
        grades_max = 0

        def fetch_grade(url):
            url = url_builder(url)
            self.browser.open(url)                
            soup = BeautifulSoup(str(self.browser.page), 'html.parser')
            title = soup.find('a', id='il_mhead_t_focus')
            d = {}
            d['title'] = title.text
            form_groups = soup.find_all('div', class_='form-group')
            for f in form_groups:
                name = f.find('div', class_='il_InfoScreenProperty')
                if name is None:
                    continue
                name = name.text
                if name != "Ende":
                    continue
                val = f.find('div', class_='il_InfoScreenPropertyValue').text
                d['deadline'] = val.strip()
            
            for potential_url in soup.find_all('a'):
                try:
                    if potential_url.text == 'Ergebnisse':
                        d['url'] = potential_url['href']
                        break
                except KeyError:
                    continue
            
            self.browser.open(url_builder(d['url']))
            soup = BeautifulSoup(str(self.browser.page), 'html.parser')
            trs = soup.find_all('tr')
            for tr in trs:
                if tr.find('strong') is not None:                
                    tds = tr.find_all('td', class_='std')
            try:
                td = tds[4].text.split(' von ')
            except UnboundLocalError:
                # No results yet / test not submitted
                grades.append(d)
                return
            d['grade'] = float(td[0])
            d['max_grade'] = float(td[1])
            
            nonlocal grades_sum, grades_max
            grades_sum += d['grade']
            grades_max += d['max_grade']              

            grades.append(d)

        threads = []
        for url in urls:
            thread = threading.Thread(target=fetch_grade, args=(url,))
            thread.start()
            threads.append(thread)

        for thread in threads:
            thread.join()

        return grades, grades_sum, grades_max
        
    def update_all_grades(self):
        threads = []
        for c in self.grades_db:
            thread = threading.Thread(target=self.fetch_assignment_grades, args=(c,))
            thread.start()
            threads.append(thread)

        for thread in threads:
            thread.join()

        self.save_db()
        
def url_builder(href: str):
    if href.startswith('http'):
        return href
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
    b.update_all_grades()
    
