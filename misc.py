import mechanicalsoup as ms
import codecs
from configparser import ConfigParser
from getpass import getpass
import tkinter as tk
from tkinter import filedialog
import openpyxl
  
def url_builder(href: str):
    if href.startswith('http'):
        return href
    return "https://ilias.hhu.de/" + href    
      
def get_id_from_url(url: str):
    return url.split('ref_id=')[1].split('&')[0]        
        
def prompt_y_n(prompt: str = None):
    return prompt_choices(choices=['y', 'n'], prompt=prompt) == 'y'

def prompt_choices(choices: list, case_sensitive: bool = False, prompt: str = None):
    return prompt_condition(lambda x: x in choices, prompt, case_sensitive=case_sensitive)

def prompt_condition(condition: callable, prompt: str = None, case_sensitive: bool = False):
    if prompt:
        print(prompt)
    choice = input('\n')
    while not condition(choice):
        print("Invalid input")
        choice = input('\n')
        if not case_sensitive:
            choice = choice.lower()
    return choice

def try_login(user, password):
    browser = ms.StatefulBrowser()

    browser.open("https://ilias.hhu.de/login.php?client_id=UniRZ&cmd=force_login&lang=de")

    browser.select_form('form[id="form_"]')
    browser["username"] = user
    browser["password"] = password
    browser.submit_selected()

    current_url = browser.get_url()
    if "ilDashboardGUI" in current_url:
        print("Login successful")
        return True
    
    print("Login failed")
    return False

def setup_config(config_path: str):
    config = ConfigParser()
    print("Setting up configuration for the first time")
    user = input("Enter your username: \n")
    print("Enter your password: ")
    password = getpass()
    while not try_login(user, password):
        user = input("Enter your username: \n")
        print("Enter your password: ")
        password = getpass()
    config['LOGIN'] = {'user': user, 'password': codecs.encode(password, 'rot_13')}
    
    print("Would you like to setup excel settings to save grades into excel tables?")
    
    if prompt_y_n():
        root = tk.Tk()
        root.withdraw()

        print("Select the excel file to save grades into")
        file_path = filedialog.askopenfilename(defaultextension=".xlsx", filetypes=[("Excel files", "*.xlsx")], title="Select the excel file to save grades into")
        while True:
            try:
                wb = openpyxl.load_workbook(file_path)
                break
            except Exception as e:
                print(f"Could not open the file {file_path}.", e)
                print("Please try again.")
                file_path = filedialog.askopenfilename(defaultextension=".xlsx", filetypes=[("Excel files", "*.xlsx")], title="Select the excel file to save grades into")

        config['EXCEL'] = {'path': file_path, 'defaul_sheet_name_length': 20}

    with open(config_path, 'w') as f:
        config.write(f)
        