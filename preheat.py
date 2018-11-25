#!/usr/bin/python
import teslajson
import time
import json
import traceback
import urllib2
import argparse
import sys

parser = argparse.ArgumentParser()
parser.add_argument('--verbose', action='count', help='Increasing levels of verbosity')
parser.add_argument('--token', help='Access token for tesla service')
parser.add_argument('--no_climate', action='store_true', help='Enable climate')
parser.add_argument('--battery', type=int, help='Percent battery to use')
parser.add_argument('--outdir', default=None, help='Directory to output log files')
args = parser.parse_args()

def refresh_vehicles(args):
    """Connect to service and get list of vehicles"""

    c = teslajson.Connection(access_token=args.token)
    if args.verbose:
        print("# Vehicles: %s\n"%str(c.vehicles))
    return c

if not args.token:
    print('''Must supply --token: Get access_token via:\ncurl -X POST -H "Cache-Control: no-cache" -H "Content-Type: multipart/form-data; boundary=----WebKitFormBoundary7MA4YWxkTrZu0gW" -F "grant_type=password" -F "client_id=81527cff06843c8634fdc09e8ac0abefb46ac849f38fe1e431c2ef2106796384" -F "client_secret=c7257eb71a564034f9419ee651c7d0e5f7aa6bfbd18bafb5c5c033b093bb2fa3" -F "email=YOUR-TESLA-LOGIN-EMAIL@SOMEWHERE.COM" -F "password=YOUR-TESLA-ACCOUNT-PASSWORD" "https://owner-api.teslamotors.com/oauth/token''')
    sys.exit(1)

c = refresh_vehicles(args)
v = c.vehicles[0]
wake_tries = 0
while wake_tries < 100000:
    vdata = v.data_request(None)
    if vdata["state"] not in ("asleep","offline","inactive"):
        break
    try:
        v.wake_up()
    except urllib2.HTTPError:
        print("# Timed out\n")
    if args.verbose:
        print("Retry wake")
    time.sleep(5)

if args.battery:
    while not v.command("set_charge_limit", {"percent": args.battery}):
        if args.verbose:
            print("Retry set_charge_limit")
        time.sleep(5)
    while not v.command('charge_start'):
        if args.verbose:
            print("Retry charge_start")
        time.sleep(5)

if not args.no_climate:
    while not v.command("auto_conditioning_start"):
        if args.verbose:
            print("Retry conditioning on")
        time.sleep(5)
