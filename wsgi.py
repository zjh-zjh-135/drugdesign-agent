import os
import sys

base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, base_dir)

from backend.app import create_app

application = create_app()

# Gunicorn 将使用这个变量名
app = application

if __name__ == '__main__':
    app.run()
