import sys
sys.path.append('..')

import main

client = None

def start_client():
    global client
    client = main.Client()

def stop_client():
    if not client is None:
        client.halt()
