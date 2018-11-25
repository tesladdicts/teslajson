#!/usr/bin/python
import json
import socket
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--verbose', action='count', help='Increasing levels of verbosity')
parser.add_argument('--cmd_address', help='address:Port number to send UDP commands to')
parser.add_argument('--variables', action='append',type=lambda x: x.split('='))
args = parser.parse_args()

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
dest = args.cmd_address.split(":")
dest[1] = int(dest[1])
sock.sendto(json.dumps(dict(args.variables)), tuple(dest))
