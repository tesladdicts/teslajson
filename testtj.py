#!/usr/bin/python
import teslajson
import time
import argparse

def refresh_vehicles(token):
    # Get token via: curl -X POST -H "Cache-Control: no-cache" -H "Content-Type: multipart/form-data; boundary=----WebKitFormBoundary7MA4YWxkTrZu0gW" -F "grant_type=password" -F "client_id=81527cff06843c8634fdc09e8ac0abefb46ac849f38fe1e431c2ef2106796384" -F "client_secret=c7257eb71a564034f9419ee651c7d0e5f7aa6bfbd18bafb5c5c033b093bb2fa3" -F "email=YOUR-TESLA-LOGIN-EMAIL@SOMEWHERE.COM" -F "password=YOUR-TESLA-ACCOUNT-PASSWORD" "https://owner-api.teslamotors.com/oauth/token"
    c = teslajson.Connection(access_token=token, retries=10)
    print "Vehicle 1: %s"%str(c.vehicles[0])
    return c

parser = argparse.ArgumentParser()
parser.add_argument('--token', help='Access token for tesla service')
args = parser.parse_args()


c = refresh_vehicles(args.token)
v = c.vehicles[0]
if v["state"] in ("asleep","offline","inactive"):
    print v.wake_up()

print str(v.data_all())
#print str(v.data_request('charge_state'))
#v.command('charge_start')
