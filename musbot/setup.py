import os
import sys
import dotenv
import logging

from systemd.journal import JournalHandler

def setup():
	path = os.path.join(os.path.dirname(__file__), '..', '.env')

	if os.path.exists(path):
		dotenv.load_dotenv(path)

	if '--debug' in sys.argv[1:]:
		handler = logging.StreamHandler()
	else:
		handler = JournalHandler()
	
	logger = logging.getLogger('root')
	logger.addHandler(handler)
	logger.setLevel(logging.INFO)