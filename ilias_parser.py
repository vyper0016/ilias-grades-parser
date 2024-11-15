from configparser import ConfigParser, NoSectionError
import codecs
import mechanicalsoup as ms
from bs4 import BeautifulSoup
import json
import threading
from prettytable import PrettyTable
import excel
from datetime import datetime, timedelta
from misc import *
import os
from halo import Halo
from fetch_grades import fetch_assignment_grades, supported
from misc import url_builder

class IliasParser:
    
    def __init__(self, config_path, new=False, **other_creds):
        config = ConfigParser()
        config.read(config_path)
        user = config.get('LOGIN', 'user')
        password = config.get('LOGIN', 'password') 
        password = codecs.decode(password, 'rot_13')
        self.browser = self.login(user, password)
        self.creds = {'user': user, 'password': password, **other_creds}
        self.supported_courses = supported
        try :
            self.zulassung_excel = config.get('EXCEL', 'path')
        except NoSectionError:
            self.zulassung_excel = None
        self.config = config
        if not self.browser:
            return
        if new:
            self.grades_db = {}
            self.excel_db = {}
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
        spinner = Halo(text='Parsing courses', spinner='bouncingBar')
        browser = self.browser
        soup = BeautifulSoup(str(browser.page), 'html.parser')
        courses = {}
        member_db = {}
        course_bodies = soup.find_all('div', class_='media-body')
        spinner.start()
        for c in course_bodies:
            d = c.find('div', class_='il-item-title')
            if d is None:
                continue
            try:
                c_url = d.find('a').get('href')
            except AttributeError:
                print('\ncould not find url for course', d.text)
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
                print('\ncould not find dozent for course', d.text)
            if dotz is not None:
                courses[c_id]['profs'] = dotz
            
            browser.open(url_builder(courses[c_id]['url']))
            c_soup = BeautifulSoup(str(browser.page), 'html.parser')
            
            members = self.parse_members(c_soup)
            if members is not None:
                member_db[c_id] = members
            
            courses[c_id]['sub_links'] = self.parse_sub_links(c_soup)

        spinner.succeed('Courses parsed')
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
                default_name = self.courses_db[course_id]['title'].split(' ')[0] + ' ' + self.courses_db[course_id]['title'].split(' ')[1]
                default_name = excel.validate_sheet_title(default_name)
                    
                sheet_name = prompt_condition(lambda x: len(x) <= 31 and excel.sheet_title_valid(x, verbose=True), "Enter a sheet name or hit Enter to use the default name: " + default_name)
                sheet_name = sheet_name if sheet_name != '' else default_name
                
                self.excel_db[course_id] = {'sheet_name': sheet_name, 'skip': False}
                self.excel_db[course_id]['number_tests'] = int(prompt_condition(lambda x: x.isdigit() and 0 < int(x) < 100, "Enter the number of tests expected for this course: "))
                self.excel_db[course_id] = excel.make_from_template(self.zulassung_excel, self.grades_db[course_id], self.excel_db[course_id])   
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
        print("All excel tables saved")
        if prompt_y_n("Would you like to open the excel file? (y/n)"):
            os.startfile(self.zulassung_excel)
                  
    def parse_members(self, course_soup):
        return
      
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
            return True     
                   
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
            
    def fetch_assignment_grades(self, course_id):
        return fetch_assignment_grades(self, course_id)     
        
def parse_dotzen(s: str):
    if 'Dozent(en):' in s:
        s = s.split('Dozent(en):')[1]
        s = s.replace(',', '')
        return s.split(';')

if __name__ == "__main__":
    config_path = './data/config.ini'
    try:
        b = IliasParser(config_path, new=False)
    except NoSectionError:
        os.makedirs('./data', exist_ok=True)
        setup_config(config_path)
        b = IliasParser(config_path, new=True)
    b.update_all_grades()
    
