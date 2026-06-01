import os
from dotenv import load_dotenv, find_dotenv
path = find_dotenv()
print('dotenv path:', path)
load_dotenv(path)
print('EMAIL_HOST_USER:', repr(os.getenv('EMAIL_HOST_USER')))
print('EMAIL_HOST_PASSWORD:', repr(os.getenv('EMAIL_HOST_PASSWORD')))
print('len password:', len(os.getenv('EMAIL_HOST_PASSWORD') or ''))
