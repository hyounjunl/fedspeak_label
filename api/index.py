from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return "API is working!"

# Import the main app
from ..index import app as main_app

# Merge the apps
for rule in main_app.url_map.iter_rules():
    app.add_url_rule(rule.rule, rule.endpoint, main_app.view_functions[rule.endpoint])