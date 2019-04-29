#!/usr/bin/python
#
# Load supercharger locations from TSV file
#

import argparse
#import datetime
#from datetime import timedelta
#import requests
#import subprocess
#import tesla_parselib
import json
import csv
import psycopg2
from psycopg2 import sql
#from psycopg2.extensions import AsIs
#from jinja2 import Environment, FileSystemLoader
#from xhtml2pdf import pisa

parser = argparse.ArgumentParser(description="Load supercharger locations from tab-separated file")
parser.add_argument('--verbose', '-v', action='count', help='Increasing levels of verbosity')
parser.add_argument('--dbconfig', type=str, default='dbconfig', help='Insert records in database using this config file')
parser.add_argument('tsvfile', type=str, help="file with data in tsv format")
args = parser.parse_args()

if args.verbose is None:
    args.verbose = 0

# connect to the database
if args.dbconfig:
    # we are going to read data from the database
    # read the config file and get database settings
    dbfile = open(args.dbconfig, "r")
    if dbfile:
        dbinfo = json.loads(dbfile.read())
        dbfile.close()
    # open the database
    try:
        dbconn = psycopg2.connect(**dbinfo)
        cursor = dbconn.cursor()
        cursor.execute("SELECT version();")
        record = cursor.fetchone()
        if args.verbose:
            print('Connected to {}'.format(str(record[0])))
        #cursor.close()
    except (Exception, psycopg2.Error) as error :
        print("Error while connecting to PostgreSQL", error)
        exit()
        
    # initialize counters
    totlocs = 0
    addedlocs = 0
    # read TSV file
    with open(args.tsvfile) as infile:
        reader = csv.reader(infile, delimiter='\t')
        # setup SQL statements
        insert_flds = ["name","latitude","longitude","is_tesla_supercharger", "is_charge_station", "is_home",
	"is_work"]
        insert_str = sql.SQL("INSERT INTO location ({}) VALUES ({})").format(sql.SQL(",").join(map(sql.Identifier, insert_flds)),sql.SQL(",").join(map(sql.Placeholder, insert_flds)))
        query = sql.SQL("SELECT location_id FROM location WHERE name={} AND latitude={} AND longitude={} AND is_tesla_supercharger={} AND is_charge_station = {} AND is_home = {} AND is_work = {}").format(sql.Placeholder(), sql.Placeholder(), sql.Placeholder(), sql.Placeholder(), sql.Placeholder(), sql.Placeholder(), sql.Placeholder() )
        # process each entry
        for row in reader:
	    totlocs = totlocs + 1
	    # check if this is already in the database
	    if args.verbose>2:
	        print cursor.mogrify(query,[row[0], row[1], row[2], row[3], row[4], row[5], row[6] ] )
	    cursor.execute(query,[row[0], row[1], row[2], row[3], row[4], row[5], row[6] ] )
	    # if there is no match we insert it
	    if cursor.rowcount<1:
	        addedlocs = addedlocs + 1
	        if args.verbose>2:
	            print cursor.mogrify(insert_str,{"name": row[0], "latitude": row[1], "longitude": row[2], "is_tesla_supercharger": row[3], "is_charge_station": row[4], "is_home": row[5], "is_work": row[6]})
                try:
                    cursor.execute(insert_str,{"name": row[0], "latitude": row[1], "longitude": row[2], "is_tesla_supercharger": row[3], "is_charge_station": row[4], "is_home": row[5], "is_work": row[6]})
                except Exception as error :
                    print("Error: failed to insert record into location: %s"%str(error))
                    dbconn.rollback()
                else:
                    dbconn.commit()
            else:
	        if args.verbose>0:
		    outstr = 'skipping duplicate ({}, {}, {}'.format(row[0], str(row[1]), str(row[2]))
	            if row[3] == 't': 
		        outstr = outstr + ', Tesla supercharger'
		    if row[4] == 't':
		        outstr = outstr + ', Charging station'
		    if row[5] == 't':
		        outstr = outstr + ', Home'
		    if row[6] == 't':
		        outstr = outstr + ', Work'
		    outstr = outstr + ')'
	            print(outstr)

    if(dbconn):
        cursor.close()
        dbconn.close()
        if args.verbose>0:
            print "PostgreSQL connection closed"
    print "Added " + str(addedlocs) + " new locations (from " + str(totlocs) + " total)"

