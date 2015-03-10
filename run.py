from bizarro import create_app
from os import environ
if __name__ == '__main__':
    app = create_app(environ, True)
    app.run(debug=True)
