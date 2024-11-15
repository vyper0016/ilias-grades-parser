from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import threading
from misc import url_builder

supported = {'1526617', '1526496', '1526715', '1526712', '1639737', '1639601', '1639723', '1735389', '1735379', '1735380'}

def fetch_assignment_grades(parser, course_id):
    course_id = str(course_id)
    
    if course_id not in parser.supported_courses:
        print(f"Course {parser.courses_db[course_id]['title']} not supported")
        return
    
    print("Fetching grades for course", parser.courses_db[course_id]['title'])
    grades = []
    grades_sum = 0
    grades_max = 0
    match course_id:
        
        case '1526617':    # Matinf 1
            parser.update_sub_links(course_id)
            for i in parser.courses_db[course_id]['sub_links']:
                if i['title'].startswith('Abgabe der'):
                    url = i['url']
                    break
            
            grades, grades_sum, grades_max = grades_template2(parser, url)         
        
        case '1526496':  # Progra
            
            firefox_options = webdriver.FirefoxOptions()
            firefox_options.add_argument("--headless")
            
            driver = webdriver.Firefox(options=firefox_options)
            
            driver.get('https://hsp.pages.cs.uni-duesseldorf.de//programmierung/website//html/points_overview.html')
            driver.find_element(By.ID, 'github_token').send_keys(parser.creds['github_token'])
            driver.find_element(By.ID, 'github_name').send_keys(parser.creds['github_user'])
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
        
        case '1526715':  # Rechnerarchitektur            
            parser.update_sub_links(course_id)

            urls = [i['url'] for i in parser.courses_db[course_id]['sub_links'] if i['title'].startswith('Übungsblatt')]
            grades, grades_sum, grades_max = grades_template1(parser, urls)

        case '1526712': # WA
            for i in parser.courses_db[course_id]['sub_links']:
                if i['title'].startswith('Übung'):
                    url = i['url']
                    break
            parser.browser.open(url)
            soup = BeautifulSoup(str(parser.browser.page), 'html.parser')
            hs = soup.find_all('h3', class_='il_ContainerItemTitle')
            urls = []
            for h in hs:
                a = h.find('a')
                if a is None:
                    continue
                if not a.text.startswith('Test'):
                    continue
                urls.append(a['href'])
            grades, grades_sum, grades_max = grades_template1(parser, urls)                
        
        case '1639737': # Propra 1
            parser.update_sub_links(course_id)
            
            urls = [i['url'] for i in parser.courses_db[course_id]['sub_links'] if i['title'].startswith('Test Woche')]
            grades, grades_sum, grades_max = grades_template1(parser, urls)
            
        case '1639601': # Matinf 2
            
            grades, grades_sum, grades_max = grades_template2(parser=parser, max_grade=30, url='https://ilias.hhu.de/ilias.php?baseClass=ilExerciseHandlerGUI&ref_id=1671344&cmd=showOverview')
            
        case '1639723': # DB
            parser.update_sub_links(course_id)
            
            urls = [i['url'] for i in parser.courses_db[course_id]['sub_links'] if i['title'].startswith('Test')]
            
            grades, grades_sum, grades_max = grades_template1(parser, urls)
        
        case '1735389': # Mafin3
            grades, grades_sum, grades_max = grades_template2(parser=parser, max_grade=30, url='https://ilias.hhu.de/ilias.php?baseClass=ilExerciseHandlerGUI&ref_id=1759928&cmd=showOverview')
            
        case '1735379': # Propra 2
            parser.update_sub_links(course_id)
            
            urls = [i['url'] for i in parser.courses_db[course_id]['sub_links'] if i['title'].startswith('Test ')]
            grades, grades_sum, grades_max = grades_template1(parser, urls)
        
        case '1735380': # aldat
            parser.update_sub_links(course_id)
            
            urls = [i['url'] for i in parser.courses_db[course_id]['sub_links'] if i['title'].startswith('Quiz ')]
            grades, grades_sum, grades_max = grades_template1(parser, urls)
        
        case _:
            print("Course not supported", course_id)
            return
        
    for g in grades:
        g['index'] = int(g['title'].split(' ')[-1])
        g['deadline'] = g['deadline'].replace('Heute', datetime.now().strftime('%d. %B %Y'))\
        .replace('Gestern', (datetime.now() - timedelta(days=1)).strftime('%d. %B %Y'))\
        .replace('Morgen', (datetime.now() + timedelta(days=1)).strftime('%d. %B %Y'))
        
        g['submitted'] = 'grade' in g   # TODO: check on ilias if submitted
    
    grades = sorted(grades, key=lambda x: x['index'])
    
    for g in grades:
        del g['index']
    
    t = {'title': parser.courses_db[course_id]['title'] ,'grades': grades, 'percentage_total': grades_sum/grades_max if grades_max != 0 else 0}
    
    print("Done fetching grades for course", t['title'])
    parser.grades_db[course_id] = t
    return t
    
def grades_template1(parser, urls):
    grades = []
    grades_sum = 0
    grades_max = 0

    def fetch_grade(url):
        url = url_builder(url)
        parser.browser.open(url)                
        soup = BeautifulSoup(str(parser.browser.page), 'html.parser')
        title = soup.find('a', id='il_mhead_t_focus')
        d = {}
        d['title'] = title.text.replace(u'\xa0', u' ')
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
        
        parser.browser.open(url_builder(d['url']))
        soup = BeautifulSoup(str(parser.browser.page), 'html.parser')
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

def grades_template2(parser, url, max_grade):
    grades = []
    grades_sum = 0
    grades_max = 0
    
    parser.browser.open(url)
    soup = BeautifulSoup(str(parser.browser.page), 'html.parser')
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