import openpyxl
import re
from configparser import ConfigParser

import openpyxl.worksheet
from worksheet_copier import copy_worksheet
from misc import url_builder
from openpyxl.formatting.rule import ColorScaleRule

TEMPLATE_PATH = './tmp/template.xlsx'
TEMPLATE_INI_PATH = './tmp/template.ini'

NAME_EQUIVALENTS = {
    'grade_titles': 'title',
    'grade_deadlines': 'deadline',
    'grade_submitted': 'submitted',
    'grade_value': 'grade',
    'grade_max': 'max_grade',
}

def get_sheet_list(file_path):
    wb = openpyxl.load_workbook(file_path)
    return wb.sheetnames

def cell_range_valid(s: str):
    return re.match(r'^[A-Z]+[0-9]+:[A-Z]+[0-9]+$', s)

def get_configs():
    config = ConfigParser()
    config.read(TEMPLATE_INI_PATH)
    d = {}
    for section in config.sections():
        d[section] = {}
        for option in config.options(section):
            d[section][option] = config.get(section, option)
    return d

def cell_range_to_list(s: str):
    if not cell_range_valid(s):
        raise ValueError('Invalid cell range')
    start, end = s.split(':')
    start_col = ord(start[0]) - ord('A')
    start_row = int(start[1:]) - 1
    end_col = ord(end[0]) - ord('A')
    end_row = int(end[1:]) - 1
    return [(chr(i + ord('A')) + str(j + 1)) for i in range(start_col, end_col + 1) for j in range(start_row, end_row + 1)]

def make_from_template(file_path, course_grades: dict, new_sheet_name: str):
    config = get_configs()
    wb_tmp = openpyxl.load_workbook(TEMPLATE_PATH)
    wb_new = openpyxl.load_workbook(file_path)
    
    if new_sheet_name in wb_new.sheetnames:
        raise ValueError('Sheet name already exists in workbook')
    
    ws_tmp = wb_tmp[config['DEFAULTS']['sheet']]
    
    ws_tmp[config['CELLS']['title']] = course_grades['title']
    
    sheet_dict = {}
    
    for attr in NAME_EQUIVALENTS:
        cells_list = cell_range_to_list(config['CELLS'][attr])
        sheet_dict[NAME_EQUIVALENTS[attr]] = config['CELLS'][attr]
        grade_key = NAME_EQUIVALENTS[attr]
        for grade, cell in zip(course_grades['grades'], cells_list):
            if grade_key not in grade:
                continue
            ws_tmp[cell] = grade[grade_key]
            if grade_key == 'title' and 'url' in grade and grade['url'] is not None:
                ws_tmp[cell].hyperlink = url_builder(grade['url'])
    
    wb_new.create_sheet(new_sheet_name)
    ws_new = wb_new[new_sheet_name]
    copy_worksheet(ws_tmp, ws_new)  # copy all the cell values and styles, does not copy conditional formatting
    
    # copy conditional formatting
    rule = ColorScaleRule(start_type='percentile', start_value=0, start_color='f8696b',
                            mid_type='percentile', mid_value=50, mid_color='b1d580',
                            end_type='percentile', end_value=100, end_color='63be7b')
    ws_new.conditional_formatting.add(config['CELLS']['to_format'], rule)
    
    save_wb_retriable(wb_new, file_path)
    
    return sheet_dict
    
def save_to_excel(file_path, course_grades: dict, course_excel_dict: dict):
    wb = openpyxl.load_workbook(file_path)
    ws = wb[course_excel_dict['sheet_name']]
    for attr in course_excel_dict['cells']:
        for grade, cell in zip(course_grades['grades'], cell_range_to_list(course_excel_dict['cells'][attr])):
            if attr not in grade:
                continue
            ws[cell] = grade[attr]
            if attr == 'title' and 'url' in grade and grade['url'] is not None:
                ws[cell].hyperlink = url_builder(grade['url'])
            if attr == 'submitted' and ws[cell].value is not None:
                continue
    
    save_wb_retriable(wb, file_path)  

def save_wb_retriable(wb, file_path):
    while True:
        try:
            wb.save(file_path)
            break
        except PermissionError:
            print(f"Could not save to {file_path}. Please close the file and press enter to retry.")
            input()
    
if __name__ == '__main__':
    import json
    with open('data/grades.json') as f:
        grades = json.load(f)
    make_from_template(r"D:\sciebo\hhu\test.xlsx", grades['1639723'], 'test')
    