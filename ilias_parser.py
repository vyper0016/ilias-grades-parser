from configparser import ConfigParser
import codecs
import mechanicalsoup as ms
from bs4 import BeautifulSoup
import json
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import threading
from prettytable import PrettyTable
import excel
from datetime import datetime
from misc import *
import os

class IliasParser:
    
    def __init__(self, config_path, new=False, **other_creds):
        config = ConfigParser()
        config.read(config_path)
        user = config.get('LOGIN', 'user')
        password = config.get('LOGIN', 'password') 
        password = codecs.decode(password, 'rot_13')
        self.browser = self.login(user, password)
        self.creds = {'user': user, 'password': password, **other_creds}
        self.supported_courses = {'1526617', '1526496', '1526715', '1526712', '1639737', '1639601', '1639723'}
        self.zulassung_excel = config.get('EXCEL', 'path')
        self.config = config
        if not self.browser:
            return
        if new:
            self.grades_db = {}
            self.parse_courses()
        else:
            try:
                with open('./data/courses.json', 'r') as f:
                    self.courses_db = json.load(f)
            except FileNotFoundError:
                self.courses_db = {}
            try:
                with open('./data/members.json', 'r') as f:
                    self.members_db = json.load(f)
            except FileNotFoundError:
                self.members_db = {}
            try:
                with open('./data/grades.json', 'r') as f:
                    self.grades_db = json.load(f)
            except FileNotFoundError:
                self.grades_db = {}
            try:
                with open('./data/excel.json', 'r') as f:
                    self.excel_db = json.load(f)
            except FileNotFoundError:
                self.excel_db = {}
            self.save_db()
          
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
            try:
                c_url = d.find('a').get('href')
            except AttributeError:
                print('could not find url for course', d.text)
                continue
            c_id = get_id_from_url(c_url)
            if c_id in courses:
                continue
            courses[c_id] = {
                'title': d.find('a').text,
                'url': c_url,
            }
            d2 = c.find('div', class_='il-item-description')
            if d2 is not None:
                dotz = parse_dotzen(d2.text)
            else:
                dotz = None
                print('could not find dotzent for course', d.text)
            if dotz is not None:
                courses[c_id]['profs'] = dotz
            
            browser.open(url_builder(courses[c_id]['url']))
            c_soup = BeautifulSoup(str(browser.page), 'html.parser')
            
            members = self.parse_members(c_soup)
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
            
        with open('./data/excel.json', 'w') as f:
            json.dump(self.excel_db, f, indent=4)
       
    def prompt_excel(self, course_id):
        print('Could not find excel data for course', self.courses_db[course_id]['title'])
        choice = prompt_choices(choices=['t', 's'], prompt="would you like to:\n\
            t: use a template to create a new excel table automatically\n\
            s: skip this course and don't save it in the excel file")
        
        match choice:
            case 's':
                self.excel_db[course_id] = {'skip': True}
            
            case 't':
                print("Creating new excel table for course", self.courses_db[course_id]['title'])
                print("What would you like the sheet name for this course to be?")
                default_name = self.courses_db[course_id]['title'][:int(self.config.get('EXCEL', 'defaul_sheet_name_length'))]
                sheet_name = prompt_condition(lambda x: len(x) <= 31, "Enter a sheet name or hit Enter to use the default name: " + default_name)
                sheet_name = sheet_name if sheet_name != '' else default_name
                
                self.excel_db[course_id] = {'sheet_name': sheet_name, 'skip': False}
                self.excel_db[course_id]['cells'] = excel.make_from_template(self.zulassung_excel, self.grades_db[course_id], sheet_name)   
                print("Excel table created for course", self.courses_db[course_id]['title'])
                
            case _:
                raise ValueError("Invalid choice")
                
        self.save_db() 
                    
    def save_excel(self):
        for course_id in self.grades_db:
            if course_id not in self.excel_db:
                self.prompt_excel(course_id)
            
            if self.excel_db[course_id]['skip']:
                continue
            
            excel.save_to_excel(self.zulassung_excel, self.grades_db[course_id], self.excel_db[course_id])
            print("Excel table saved for course", self.courses_db[course_id]['title'])
                  
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
        
        if course_id not in self.supported_courses:
            print(f"Course {self.courses_db[course_id]['title']} not supported")
            return
        
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
            
            grades, grades_sum, grades_max = self.grades_template2(url)         
        
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
        
        elif course_id == '1639737': # Propra 1
            self.update_sub_links(course_id)
            
            urls = [i['url'] for i in self.courses_db[course_id]['sub_links'] if i['title'].startswith('Test Woche')]
            grades, grades_sum, grades_max = self.grades_template1(urls)
            
        elif course_id == '1639601': # Matinf 2
            
            grades, grades_sum, grades_max = self.grades_template2(max_grade=30, url='https://ilias.hhu.de/ilias.php?baseClass=ilExerciseHandlerGUI&ref_id=1671344&cmd=showOverview')
            
        elif course_id == '1639723': # DB
            self.update_sub_links(course_id)
            
            urls = [i['url'] for i in self.courses_db[course_id]['sub_links'] if i['title'].startswith('Test')]
            
            grades, grades_sum, grades_max = self.grades_template1(urls)
        for g in grades:
            g['index'] = int(g['title'].split(' ')[-1])
            g['deadline'] = g['deadline'].replace('Heute', datetime.now().strftime('%d. %B %Y'))
            g['submitted'] = 'grade' in g   # TODO: check on ilias if submitted
        
        grades = sorted(grades, key=lambda x: x['index'])
        
        for g in grades:
            del g['index']
        
        t = {'title': self.courses_db[course_id]['title'] ,'grades': grades, 'percentage_total': grades_sum/grades_max}
        
        print("Done fetching grades for course", t['title'])
        self.grades_db[course_id] = t
        return t
            
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
     
    def grades_template2(self, url, max_grade):
        grades = []
        grades_sum = 0
        grades_max = 0
        
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
                if name not in {"Note", "Beendet am", "Abgabetermin", "Abgegebene Dateien"}:
                    continue
                val = f.find('div', class_='il_InfoScreenPropertyValue').text
                
                if name == "Note":
                    d['grade'] = float(val)
                elif name == "Beendet am":
                    d['deadline'] = val.strip()
                elif name == "Abgabetermin":
                    d['deadline'] = val.strip()
                elif name == "Abgegebene Dateien":
                    d['submitted'] = "Sie haben noch keine Datei abgegeben." not in val
            
            try:
                grades_sum += d['grade']                      
            except KeyError:
                pass
            d['max_grade'] = max_grade
            d['url'] = url
            grades.append(d)
            grades_max += max_grade
        return grades, grades_sum, grades_max
    
    def prompt_course_selection(self):
        print("No grades found in database")
            
        if prompt_y_n("Would you like to choose courses to fetch grades for? (y/n)"):
            courses = []
            courses_table = PrettyTable()
            courses_table.field_names = ['Index', 'Course ID', 'Course Title', 'Supported']

            for i, course_id in enumerate(self.courses_db):
                course = self.courses_db[course_id]
                supported = 'X' if course_id in self.supported_courses else ''
                courses_table.add_row([i+1, course_id, course['title'], supported])
                courses.append(course_id)
                
            print(courses_table)
            print("Enter the indeces of the courses you want to fetch grades for separated by commas")
            
            while True:
                try:
                    choices = [int(i) for i in input().replace(' ', '').split(',')]
                    if not choices or len(choices) > len(courses):
                        print("Invalid input")
                        continue
                    break
                except ValueError:
                    print("Invalid input")
            
            for choice in choices:
                self.grades_db[courses[choice-1]] = {}          
                   
    def update_all_grades(self):
        threads = []
        if not self.grades_db:
            if self.prompt_course_selection() is None:
                return
                    
        for c in self.grades_db:
            thread = threading.Thread(target=self.fetch_assignment_grades, args=(c,))
            thread.start()
            threads.append(thread)

        for thread in threads:
            thread.join()

        self.save_db()
        
        if self.zulassung_excel:
            self.save_excel()      
        
def parse_dotzen(s: str):
    if 'Dozent(en):' in s:
        s = s.split('Dozent(en):')[1]
        s = s.replace(',', '')
        return s.split(';')

if __name__ == "__main__":
    config_path = './data/config.ini'
    try:
        b = IliasParser(config_path, new=False)
    except FileNotFoundError:
        os.makedirs('./data', exist_ok=True)
        setup_config(config_path)
        b = IliasParser(config_path, new=True)
    b.update_all_grades()
    
