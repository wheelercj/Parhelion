# Source of the code in this file: https://ritza.co/showcase/repl.it/building-a-discord-bot-with-python-and-repl-it.html

from flask import Flask
from threading import Thread


app = Flask('')


@app.route('/')
def home():
    return 'The bot\'s web server is online.'


def run():
    app.run(host='0.0.0.0', port=8080)


def keep_alive():
    t = Thread(target=run)
    t.start()
