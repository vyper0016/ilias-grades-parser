import eel
from jinja2 import Environment, FileSystemLoader
import os
from time import sleep

data = {'name': 'John Doe'}

eel.init('web')
template_loader = FileSystemLoader(searchpath="./web/templates")
jinja_env = Environment(loader=template_loader)

last_page = 'index'

def delete_rendered_page(page_name):
    os.remove('./web/html/'+page_name+'.html')

def save_html(html, file_name):
    with open(file_name, 'w') as f:
        f.write(html)

def render_template(template_name, data, save=True):
    template = jinja_env.get_template(template_name + '.html')
    data = template.render(data)
    if save:
        save_html(data, './web/html/'+template_name+'.html')
        print(f'Saved {template_name}.html')

@eel.expose
def prepare_page(page_name):
    global last_page
    match page_name:
        case 'index':
            render_template(page_name, data)
        case 'p2':
            render_template(page_name, {"pp": "pp name"})
            
    delete_rendered_page(last_page)
    last_page = page_name

render_template('index', data, save=True)
eel.start('./html/index.html', mode='default')