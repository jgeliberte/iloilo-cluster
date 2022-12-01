"""
File Runner of the whole server
Contains the Flask App initialization function
"""

from connection import create_app, SOCKETIO
import os
from argparse import ArgumentParser

# from gevent import monkey
# monkey.patch_all()


#PARSER = ArgumentParser(description="Run Dynaslope 3.0 Server")
#PARSER.add_argument(
#    "-sm", "--skip_memcache", help="skip memcache initialization", action="store_true")
#PARSER.add_argument(
#    "-ew", "--enable_webdriver", help="start running Chrome of webdriver",
#    action="store_true")
#ARGS = PARSER.parse_args()


CONFIG_NAME = os.getenv("FLASK_CONFIG")
APP = create_app(CONFIG_NAME, skip_memcache=False,enable_webdriver=False)

# Staging branch
if __name__ == "__main__":
    print("Flask server is now running...")
    APP.run(host="0.0.0.0", port=5000, debug=True)
#    SOCKETIO.run(APP, host='127.0.0.1', port=5000,
#                 debug=True, use_reloader=False)
