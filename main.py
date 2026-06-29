import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

import eel
from gui.web_backend import expose_functions   # импортируем функции для Eel

if __name__ == '__main__':
    # Папка с фронтендом
    web_dir = os.path.join(os.path.dirname(__file__), 'src', 'gui', 'web_ui')
    eel.init(web_dir)
    
    # Регистрируем Python-функции, доступные из JS
    expose_functions()
    
    # Запускаем приложение (откроется в родном окне браузера, но Eel умеет и в Chrome/Edge окно)
    eel.start('index.html', mode='chrome', size=(800, 650), port=0)