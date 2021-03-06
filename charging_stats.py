#!/usr/bin/python
#
# Print charging statistics for last n days (default 7)
#

import math
import argparse
import datetime
from datetime import timedelta
#import requests
#import subprocess
#import tesla_parselib
import json
import psycopg2
from psycopg2.extensions import AsIs
from jinja2 import Environment, FileSystemLoader
from xhtml2pdf import pisa

def toRad(degree):
    """convert degrees to radians"""
    try:
        d = float(degree)  
    except ValueError:
        return None
    else:
        return d*math.pi/180

parser = argparse.ArgumentParser(description="Print charging statistics for last n days")
parser.add_argument('--verbose', '-v', action='count', help='Increasing levels of verbosity')
parser.add_argument('--days', '-d', type=int, default=7, nargs='?')
parser.add_argument('--dbconfig', type=str, default='dbconfig', help='Insert records in database using this config file')
parser.add_argument('--format', '-f', type=str, default='txt', choices=['txt', 'tsv', 'pdf', 'html'], help='output file format')
parser.add_argument('vehicle', type=str, help="vehicle name or vehicle id")
args = parser.parse_args()

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
            print('Connected to {}\n'.format(str(record[0])))
        #cursor.close()
    except (Exception, psycopg2.Error) as error :
        print("Error while connecting to PostgreSQL", error)
        exit()

    # select the vehicle
    # first check by name
    query = "SELECT vehicle_id, display_name AS name FROM vehicle WHERE display_name=%s"
    cursor.execute(query,(args.vehicle,))
    # if there is no match we try vehicle_id
    if cursor.rowcount<1:
        # check if the vehicle can be converted to a long
        try:
	    vid = long(float(args.vehicle))
	except: 
	    # it is not a number use None to mean NULL, which will fail
	    vid = None
        query = "SELECT vehicle_id, display_name AS name FROM vehicle WHERE vehicle_id=%s"
        cursor.execute(query,(vid,))
        # if no matches then exit with an error
        if cursor.rowcount<1:
	    print 'No car with id or name matching {}.'.format(args.vehicle)							
	    cursor.close()
	    dbconn.close()
	    exit()
    # we will use the first match
    res = cursor.fetchone()
    vehicle_id = res[0]
    display_name = res[1]
    # if the car is not named we will use the ID as name
    if len(display_name)==0 :
        display_name = vehicle_id
    # TODO: we can get other info about the car to beautify displays (eg color, etc)
    if args.verbose>0:
	print 'Computing statistics for {} (vehicle id {}).'.format(display_name, vehicle_id)

    # up to here the code was the same as for other stats scripts
    # from this point forward this is particular to charging

    # compute date from which to select
    tdelta = timedelta(days=args.days)
    now = datetime.datetime.now()
    qtime = now - tdelta
    
    # make a query to get the first row of charging and the last after charging
    query='SELECT * FROM ( SELECT timets, LAG(timets) OVER (ORDER BY timets ASC) as tb, charge_miles_added, charge_energy_added, battery_range, est_battery_range, usable_battery_level, latitude, longitude, odometer, charging_state,  LAG(charging_state) OVER (ORDER BY timets ASC) as prev FROM vehicle_status WHERE vehicle_id=%s AND timets > %s AND charging_state IS NOT NULL ) x WHERE (prev <> \'Charging\' AND charging_state = \'Charging\') OR (prev = \'Charging\' AND charging_state <> \'Charging\')'
    if args.verbose>2:
        print cursor.mogrify(query,(vehicle_id,qtime))
    cursor.execute(query,(vehicle_id,qtime))
    nrows = cursor.rowcount
    if nrows < 1:
        print 'no charging sessions in this time period'
    else:
        kwh_total = 0
        miles_total = 0
        tspantotal = 0.0
        res = cursor.fetchall()
        # if the first row is not 'Charging' then we started in the middle of a charging session, ignore
        if res[0][10] <> 'Charging':
            s = 1
            if args.verbose>0:
                print 'Ignoring first session because it started before this time period (ended {})'.format(res[0][0])
        else:
            s = 0
        n=0
        plist = []
        # go over all charging sessions started in this period
        # collect details for each session
        for i in range(s, nrows-1, 2):
            tspan = (res[i+1][1] - res[i][0]).total_seconds()
            # if we charged for no time, ignore this entry
            if tspan==0 : continue
            tspantotal = tspantotal + tspan
            tspanh = int(tspan//3600)
            tspanm = int((tspan%3600) // 60)
            toprint = {}
            n = n + 1
            tm = res[i+1][2]-res[i][2]
            #TODO: if total miles added is zero there is some problem with this entry!!
            miles_total = miles_total + tm
            tk = res[i+1][3]-res[i][3]
            kwh_total = kwh_total + tk
            # let's get the full time series for this session
            query2='SELECT timets, usable_battery_level, inside_temp, outside_temp FROM vehicle_status WHERE vehicle_id = %s AND timets >= %s AND timets <= %s'
            # let's get the temperature time series for this session
            query2='SELECT timets, usable_battery_level, inside_temp, outside_temp FROM vehicle_status WHERE vehicle_id = %s AND timets >= %s AND timets <= %s AND inside_temp IS NOT NULL'
            # let's get the average temperatures
            query2='SELECT AVG(inside_temp), AVG(outside_temp) FROM vehicle_status WHERE vehicle_id = %s AND timets >= %s AND timets <= %s'
            cursor.execute(query2,(vehicle_id,str(res[i][1]),str(res[i+1][0])))
            chtavg = cursor.fetchall()
            toprint['no'] = "%2d"%(n)
            toprint['sdate'] = res[i][0].strftime('%Y-%m-%d')
            toprint['stime'] = res[i][0].strftime('%H:%M:%S %Z')
            toprint['th'] = tspanh
            toprint['tm'] = tspanm
            # check if there is a location in the database within 180m of where we charged
            # applying the method in http://janmatuschek.de/LatitudeLongitudeBoundingCoordinates
            # assuming that the location is not close to the poles (this is fairly safe since 
            # the poles don't have superchargers, homes or work within 180m...)
            if res[i][7] is not None and res[i][8] is not None:
	        latr = toRad(res[i][7])
	        lonr = toRad(res[i][8])
	        dd = 180.0/6378137.0
	        latmin = latr - dd
	        latmax = latr + dd
	        deltalon = math.asin(math.sin(dd)/math.cos(latr))
	        lonmin = lonr - deltalon
	        lonmax = lonr + deltalon
	        locquery='SELECT name, is_tesla_supercharger, is_charge_station, is_home, is_work FROM location WHERE (latrad >= %s AND latrad <= %s) AND (lonrad >= %s AND lonrad <= %s) AND acos(sin(%s) * sin(latrad) + cos(%s) * cos(latrad) * cos(lonrad - (%s))) <= %s'
	        cursor.execute(locquery,(latmin,latmax,lonmin,lonmax,latr,latr,lonr,dd))
	        nlocs = cursor.rowcount
	        if nlocs > 0:
		    locstr = ""
		    locinfo = cursor.fetchone()
		    if locinfo[1]:
		        if args.format == "pdf":
			    locstr = "<img src=\"data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAkAAAAJCAIAAABv85FHAAAACXBIWXMAAAsTAAALEwEAmpwYAAAAB3RJTUUH4wUdAgcysoXQlwAAAM9JREFUCNc1j7FqwlAARU8igUYRIZm62KVTcXmF/IE4B/wlR1dxcPUPnB0k4iK+R5AOLaW4VSiFwiu0dch1eHQ8557lIkmSt/ZozA6eiuK7roNE0mtZbqCCCg5JUsHzaCQJb+0GtrAF125/LpcBz7NZdDTmy7kI0iR5vFxsq/XTNEDa7cbeuQiA+9UKGJxOAuDP+7hXFAHexmNg3++HNM3z+G6xaADolWWdZQAguJ1MIkkvw+HHen0Dv/9DZsyDtYQr79PpodPZgcvz83we5BXLUWhaegmlLgAAAABJRU5ErkJggg==\" />&nbsp; "
		        if args.format == "html":
			    locstr = "<img src=\"data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAIAAACQkWg2AAAACXBIWXMAAAsTAAALEwEAmpwYAAAAB3RJTUUH4wUdAiQdp/2arwAAAcZJREFUKM9tksFK41AUhv97U66xJDXFYoNUEOpuBBHdFqGbgKCYBxAHtdJViRufwXdo9RUq7nThJrizC3GwzEA1VpEKhaadmWqDyZ1FpyG9+HNX53xw7n/OTzjnGMl7fu7Y9t/Ly+7ZGYCprS3FMLRcjmUyIQM+kmNZNcZuAOHVJiYcywoxMpzgFArtSoVgXJSy2Vnv5YUDqf39+XIZAAXwZFlf0MDU+rrf7QIgQLtSeTo8BEAGzeaPhQXueVGUA8nNzfTR0c+1Nfj+sEgmJxcfHqhr2wINQM5ms9Vqu1wOaQD8/d29upKKivJxexulY+n0Yr3udzq/trclwZSiSN8fH/lgEJYkTft2dxdLJqmqqisrf66vhzb+791xKCJ3ACAlEv1aDYSA8/jqqt/rjY0IApowzWjFazbrGxufrVbQ798vL/uuG+0mTJOqhiE41nd2YjMz90tLn29vQks1DKrlcoSxyJ+kVKHQMM2PRkOgiSxr+Txlc3PTxWLoQ4rHW8fH7vm5cEcOTB8cMF0fRWNvr316SgCWyXivrwgCgU7t7s6fnIyHr1T6Onyy7JRKYvjCeLu2/fvioletDneiGoaWzzNdD5l/hLzmoFwJ0yQAAAAASUVORK5CYII=\" />&nbsp; "
			else:
		            locstr = "Supercharger: "
		    else:
		        if locinfo[2]:
			    locstr = "Charger: "
		    if locinfo[3]:
		        locstr = locstr + "Home"
		    else:
		        if locinfo[4]:
			    locstr = locstr + "Work"
			else:
			    locstr = locstr + locinfo[0]
		    if nlocs > 1:
		        locstr = locstr + " *"
		    toprint['loc'] = locstr
		else:
		    toprint['loc'] = str(res[i][7]) + "," + str(res[i][8])
	    else:
	        toprint['loc'] = "unknown location"
            toprint['tin'] = "%.1f"%(chtavg[0][0])
            toprint['tout'] = "%.1f"%(chtavg[0][1])
            toprint['smiles'] = str(res[i][4])
            toprint['emiles'] = str(res[i+1][4])
            toprint['tmiles'] = str(tm)
            toprint['mph'] = "%.1f"%(tm/(tspan/3600))
            toprint['spct'] = str(res[i][6])
            toprint['epct'] = str(res[i+1][6])
            toprint['tkwh'] =  str(tk)
            toprint['tkw'] = "%.1f"%(tk/(tspan/3600))
            # add this item to the print list
            plist.append(toprint)
            # find out what is at this location
            #overpass_url = 'https://nominatim.openstreetmap.org/reverse'
	    #response = requests.get(overpass_url, params={'format': 'jsonv2', 'lat': str(res[i][7]), 'lon': str(res[i][8]) })
	    #data = response.json()
	    #print data['display_name']
	# print totals and averages
        tspanh = int(tspantotal//3600)
        tspanm = int(tspantotal%3600//60)
	rep_kwh_total = "%.2f"%(kwh_total)
	rep_miles_total = "%.2f"%(miles_total)
	rep_mph = "%.1f"%(miles_total/(tspantotal/3600))
	# prepare jinja2 with the right template
        file_loader = FileSystemLoader('templates')
        j2env = Environment(loader=file_loader)
        if args.format == 'txt' :
	    txttemplate = j2env.get_template('charging_session.txt')
            report = txttemplate.render(
	      title='{} charging sessions in the last {} days'.format(display_name, args.days), description='Summary of Tesla vehicle charging sessions',name=display_name, datefrom=qtime.strftime("%Y/%m/%d %H:%M:%S"), dateto=now.strftime("%Y/%m/%d %H:%M:%S"), days=args.days, kwh_total=rep_kwh_total, miles_total=rep_miles_total, tspanh=tspanh, tspanm=tspanm, mph=rep_mph, plist=plist)
	    print report
	else :
	     if args.format == 'tsv' :
	         fbase = '{}-charging-{}-{}'.format(display_name,qtime.strftime("%Y-%m-%d %H:%M"),now.strftime("%Y-%m-%d %H:%M"))
	         fname = '{}.tsv'.format(fbase)
	         ofile = open(fname, "w+b")
		 txttemplate = j2env.get_template('charging_session.tsv')
                 report = txttemplate.render(
	           title='{} charging sessions in the last {} days'.format(display_name, args.days), description='Summary of Tesla vehicle charging sessions',name=display_name, datefrom=qtime.strftime("%Y/%m/%d %H:%M:%S"), dateto=now.strftime("%Y/%m/%d %H:%M:%S"), days=args.days, kwh_total=rep_kwh_total, miles_total=rep_miles_total, tspanh=tspanh, tspanm=tspanm, mph=rep_mph, plist=plist)
	         ofile.write(report)
	         ofile.close()
	     else :
	         fbase = '{} charging {} - {}'.format(display_name,qtime.strftime("%Y-%m-%d %H:%M"),now.strftime("%Y-%m-%d %H:%M"))
	         if args.format == 'pdf' : 
		     templatename = 'charging_session_pdf.xhtml'
		 else: 
		     templatename = 'charging_session.xhtml'
		 htmltemplate = j2env.get_template(templatename)
		 report = htmltemplate.render(
		   title='{} charging sessions in the last {} days'.format(display_name, args.days),
		   description='Summary of Tesla vehicle charging sessions',
		   name=display_name, datefrom=qtime.strftime("%Y/%m/%d %H:%M:%S"),
		   dateto=now.strftime("%Y/%m/%d %H:%M:%S"), 
		   days=args.days, 
		   kwh_total=rep_kwh_total, 
		   miles_total=rep_miles_total, 
		   tspanh=tspanh, 
		   tspanm=tspanm, 
		   mph=rep_mph, 
		   plist=plist)
	         if args.format == 'html' :
		     fname = '{}.html'.format(fbase)
	             ofile = open(fname, 'w')
	             ofile.write(report)
	             ofile.close()
	         if args.format == 'pdf' :
		     fname = '{}.pdf'.format(fbase)
	             ofile = open(fname, "w+b")
	             # convert HTML to PDF
	             pisaStatus = pisa.CreatePDF(report,dest=ofile)
	             ofile.close()
	             # TODO: with pisaStatus.err here

    if(dbconn):
        cursor.close()
        dbconn.close()
        if args.verbose>0:
            print "PostgreSQL connection closed\n"

