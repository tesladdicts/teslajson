#!/usr/bin/python
#
# Print the data stored by tesla_poller
#

import argparse
import datetime
import subprocess
import tesla_parselib
import json
import psycopg2

parser = argparse.ArgumentParser()
parser.add_argument('--verbose', '-v', action='count', help='Increasing levels of verbosity')
parser.add_argument('--nosummary', action='store_true', help='Do not print summary information')
parser.add_argument('--follow', '-f', type=str, help='Follow this specific file')
parser.add_argument('--numlines', '-n', type=str, help='Handle these number of lines')
parser.add_argument('--outdir', default=None, help='Convert input files into daily output files')
parser.add_argument('--dbconfig', '-d', type=str, help='Insert records in database using this config file')
parser.add_argument('files', nargs='*')
args = parser.parse_args()

if not args.numlines:
    args.numlines = "10"

if args.follow:
    args.files.append(None)

if args.dbconfig:
    # we are going to write data to the database
    # read the config file and get database settings
    dbfile = open(args.dbconfig, "r")
    if dbfile:
        dbinfo = json.loads(dbfile.read())
        dbfile.close()
        if 'host' in dbinfo:
            host = dbinfo['host']
        else:
            host = "localhost"
        if 'port' in dbinfo:
            port = dbinfo['port']
        else:
            port = "5432"
        if 'user' in dbinfo:
            user = dbinfo['user']
        else:
            user = "teslauser"
        if 'password' in dbinfo:
            password = dbinfo['password']
        else:
            password = ""
    # open the database
    try:
        conn_string = "host="+ host + " port=" + port + " dbname=tesladata  user=" + user +" password=" + password
        dbconn = psycopg2.connect(conn_string)
        cursor = dbconn.cursor()
        cursor.execute("SELECT version();")
        record = cursor.fetchone()
        print 'Connected to {}\n'.format(str(record[0]))
    except (Exception, psycopg2.Error) as error :
        print("Error while connecting to PostgreSQL", error)
        exit()
#    if(dbconn):
#        cursor.close()
#        dbconn.close()
#        print("PostgreSQL connection closed\n")



class openfile(object):
    """Open a file"""
    def __init__(self, filename, args):
        self.filename = filename
        if filename:
            self.fd = open(filename, "r")
            self.sub = None
        else:
            self.sub = subprocess.Popen(['tail','-n', args.numlines, '-F', args.follow], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.fd = self.sub.stdout

    def __enter__(self):
        return self.fd

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.filename:
            self.fd.close()
        else:
            self.sub.kill()


nexthour = 0
X = None
def output_maintenance(cur):
    global nexthour, X
    import time
    if not args.outdir:
        return
    if cur < nexthour:
        return
    if X is not None:
        X.close()
    nexthour = (int(cur / 3600)+1) * 3600
    fname = time.strftime("%Y-%m-%d.json", time.gmtime(cur))
    pname = "%s/%s"%(args.outdir, fname)
    X = open(pname, "a", 0)
    subprocess.call(["ln", "-sf", fname, "%s/cur.json"%args.outdir])


def outputit(this):
    if this.usable_battery_level:
        bat="%3d%%/%.2fM"%(this.usable_battery_level,this.battery_range)
    else:
        bat=""

    if this.charge_energy_added:
        add = "%5.2f/%.1fM"%(this.charge_energy_added, this.charge_miles_added)
    else:
        add = ""

    if this.charge_rate:
        rate = "%dkW/%dM"%(this.charger_power or 0,this.charge_rate)
    else:
        rate=""

    print("%s %-8s odo=%-7s spd=%-3s bat=%-12s chg@%-12s add=%s"%
          (datetime.datetime.fromtimestamp(this.time).strftime('%Y-%m-%d %H:%M:%S'),
           this.mode,
           "%.2f"%this.odometer if this.odometer else "",
           str(this.speed or ""),
           bat,
           rate,
           add))


firstthismode = None
lastprevmode = None
save = None
lastthis = None
reallasttime = None

# loop over all files
for fname in args.files:
    with openfile(fname, args) as R:
        linenum=0
        # loop over all json records (one per line)
        while True:
	    # read a line
            line = R.readline()
            linenum += 1
            if not line:
                break
	    # parse the json into 'this' object
            this = tesla_parselib.tesla_record(line, want_offline=args.verbose>2)

            # if no valid object move on to the next
            if not this:
                continue

            # if we are using the database fill it up!
            if args.dbconfig:
	        # check if this vehicle_id is already in the vehicle table
#	        try:
		query = 'SELECT * FROM vehicle WHERE vehicle_id={};'.format(this.vehicle_id)
		cursor.execute(query)
		if cursor.rowcount<1:
		    print ("rowcount ",cursor.rowcount)
		    # this is the first time we've seen this car, add it
		    query = "INSERT INTO vehicle (vehicle_id, vin, display_name, car_type, car_special_type, perf_config, has_ludicrous_mode, wheel_type, has_air_suspension, exterior_color, option_codes, car_version) VALUES"+this.sql_vehicle_value()+";"
		    #print query
		    try:
		        cursor.execute(query)
		        dbconn.commit()
		    except (Exception, psycopg2.Error) as error :
		        if(dbconn):
			    print("Failed to insert record into vehicle table", error)
	        else:
		    # we've already got this car, check if anything changed
		    res = cursor.fetchone()
		    updateargs = ""
		    # we assume vin will never change, so we don't check on it
		    # if attributes are in json, check to see if they have changed
		    if res[2] != this.display_name:
		        print 'This car\'s name has changed from \'{}\' to \'{}\'!\n'.format(res[2], this.display_name)		        
		        updateargs = " display_name = '" + this.display_name + "'"
		    # check car_type
		    if this.car_type is not None :
		        if res[3] != this.car_type:
		            print 'car_type has changed from \'{}\' to \'{}\'!\n'.format(res[3], this.car_type)
		            if( len(updateargs) > 1 ):
		                updateargs = updateargs + ","
		            updateargs = updateargs + " car_type = '" + this.car_type + "'"
		    # check car_special_type
		    if this.car_special_type is not None :
		        if res[4] != this.car_special_type:
		            print 'car_special_type has changed from \'{}\' to \'{}\'!\n'.format(res[4], this.car_special_type)
		            if( len(updateargs) > 1 ):
		                updateargs = updateargs + ","
		            updateargs = updateargs + " car_special_type = '" + this.car_special_type + "'"
		    # check perf_config
		    if this.perf_config is not None :
		        if res[5] != this.perf_config:
		            print 'perf_config has changed from \'{}\' to \'{}\'!\n'.format(res[5], this.perf_config)
		            if( len(updateargs) > 1 ):
		                updateargs = updateargs + ","
		            updateargs = updateargs + " perf_config = '" + this.perf_config + "'"
		    # check has_ludicrous_mode
		    if this.has_ludicrous_mode is not None :
			if res[6] != this.has_ludicrous_mode:
		            print 'has_ludicrous_mode has changed from \'{}\' to \'{}\'!\n'.format(res[6], this.has_ludicrous_mode)
		            if( len(updateargs) > 1 ):
		                updateargs = updateargs + ","
		            updateargs = updateargs + " has_ludicrous_mode = " + str(this.has_ludicrous_mode)
		    # check wheel_type
		    if this.wheel_type is not None :
		        if res[7] != this.wheel_type:
		            print 'wheel_type has changed from \'{}\' to \'{}\'!\n'.format(res[7], this.wheel_type)
		            if( len(updateargs) > 1 ):
		                updateargs = updateargs + ","
		            updateargs = updateargs + " wheel_type = '" + this.wheel_type + "'"
		    # check has_air_suspension
		    if this.has_air_suspension is not None :
			if res[8] != this.has_air_suspension:
		            print 'has_ludicrous_mode has changed from \'{}\' to \'{}\'!\n'.format(res[8], this.has_air_suspension)
		            if( len(updateargs) > 1 ):
		                updateargs = updateargs + ","
		            updateargs = updateargs + " has_air_suspension = " + str(this.has_air_suspension)
		    # check exterior_color
		    if this.exterior_color is not None :
		        if res[9] != this.exterior_color:
		            print 'exterior_color has changed from \'{}\' to \'{}\'!\n'.format(res[9], this.exterior_color)
		            if( len(updateargs) > 1 ):
		                updateargs = updateargs + ","
		            updateargs = updateargs + " exterior_color = '" + this.exterior_color + "'"
		    # check option_codes
		    if this.option_codes is not None :
		        if res[10] != this.option_codes:
		            print 'option_codes has changed from \'{}\' to \'{}\'!\n'.format(res[10], this.option_codes)
		            if( len(updateargs) > 1 ):
		                updateargs = updateargs + ","
		            updateargs = updateargs + " option_codes = '" + this.option_codes + "'"
		    # check car_version
		    if this.car_version is not None :
		        if res[11] != this.car_version:
		            print 'car_version has changed from \'{}\' to \'{}\'!\n'.format(res[11], this.car_version)
		            if( len(updateargs) > 1 ):
		                updateargs = updateargs + ","
		            updateargs = updateargs + " car_version = '" + this.car_version + "'"
		    # update the row if needed
		    if( len(updateargs) > 1 ):
		        query = 'UPDATE vehicle SET {} WHERE vehicle_id = {};'.format( updateargs, this.vehicle_id)
		        print query
		        try:
		            cursor.execute(query)
		            dbconn.commit()
		        except (Exception, psycopg2.Error) as error :
		            if(dbconn):
			        print("Failed to insert record into vehicle table", error)
		    # add a new vehicle_status row
		    query = 'INSERT INTO vehicle_status (ts, vehicle_id, state, car_locked, odometer, is_user_present, shift_state, speed, latitude, longitude, heading, gps_as_of, charging_state, battery_level. battery_range, est_battery_range, charge_rate, miles_added, energy_added, charge_current_request. charger_power, charger_voltage, inside_temp, outside_temp, climate_on, battery_heater, valet_mode) VALUES '

            # output data to file in outdir
            if args.outdir:
                output_maintenance(this.time)
                X.write(line)

            if this.mode == "Polling":
                reallasttime = this.time
                if args.verbose > 1:
                    outputit(this)
                continue

            if save:
                save = save + this
            else:
                save = this
                prev = this

            # analyze data and provide a summary
            while firstthismode and not args.nosummary:
                if firstthismode.mode != this.mode:

                    if reallasttime:
                        this.time = reallasttime
                        reallasttime = None

                    firstthismodetime = datetime.datetime.fromtimestamp(firstthismode.time)
                    thistime = datetime.datetime.fromtimestamp(save.time)
                    if not lastprevmode or not lastprevmode.usable_battery_level or not lastprevmode.odometer:
                        print("%s            ending %s, but did not have previous state to compute deltas"%
                              (firstthismodetime.strftime('%Y-%m-%d %H:%M:%S'), firstthismode.mode))
                    elif firstthismode.mode == "Charging":
                        battery_range = save.battery_range if save.battery_range > lastthis.battery_range else lastthis.battery_range
                        if this.usable_battery_level > save.usable_battery_level:
                            usable_battery_level = this.usable_battery_level
                        elif save.usable_battery_level > lastthis.usable_battery_level:
                            usable_battery_level = save.usable_battery_level
                        else:
                            usable_battery_level = lastthis.usable_battery_level

                        usable_battery_level = save.usable_battery_level if save.usable_battery_level > lastthis.usable_battery_level else lastthis.usable_battery_level
                        dblevel = usable_battery_level - lastprevmode.usable_battery_level

                        print("%s +%-16s Charged   %3d%% (to %3d%%) %5.2fkW %5.1fM (%3dmph, %4.1fkW %5.1fM max)"%
                              (firstthismodetime.strftime('%Y-%m-%d %H:%M:%S'),
                               str(thistime-firstthismodetime),
                               dblevel,
                               usable_battery_level,
                               save.charge_energy_added,
                               battery_range - lastprevmode.battery_range,
                               ((battery_range - lastprevmode.battery_range)*3600.0 /
                                (thistime-firstthismodetime).total_seconds()),
                               (save.charge_energy_added * 100.0 /
                                (dblevel)) if dblevel > 0 else -0,
                               battery_range * 100.0 / save.usable_battery_level))
                    elif firstthismode.mode == "Driving":
                        if not this.odometer:
                            break
                        battery_range = save.battery_range if save.battery_range < lastthis.battery_range else lastthis.battery_range
                        usable_battery_level = save.usable_battery_level if save.usable_battery_level < lastthis.usable_battery_level else lastthis.usable_battery_level
                        dodo = save.odometer - lastprevmode.odometer
                        drange = lastprevmode.battery_range - battery_range

                        if dodo > -1:
                            print("%s +%-16s Drove  %6.2fM at cost of %2.0f%% %5.1fM at %5.1f%% efficiency"%
                                  (firstthismodetime.strftime('%Y-%m-%d %H:%M:%S'),
                                   str(thistime-firstthismodetime),
                                   dodo,
                                   lastprevmode.usable_battery_level - usable_battery_level,
                                   drange,
                                   dodo * 100.0 / drange if drange > 0 else -0))
                    elif firstthismode.mode == "Standby":
                        battery_range = save.battery_range if save.battery_range < lastthis.battery_range else lastthis.battery_range
                        usable_battery_level = lastthis.usable_battery_level
                        drange = lastprevmode.battery_range - battery_range
                        print("%s +%-16s Sat&Lost %2.0f%% %5.1fM or %5.1fM/d (to %3d%%)"%
                              (firstthismodetime.strftime('%Y-%m-%d %H:%M:%S'),
                               str(thistime-firstthismodetime),
                               lastprevmode.usable_battery_level - usable_battery_level,
                               drange,
                               drange / (((thistime-firstthismodetime).total_seconds()) / 86400.0),
                               usable_battery_level))
                    elif firstthismode.mode == "Conditioning":
                        battery_range = save.battery_range if save.battery_range < lastthis.battery_range else lastthis.battery_range
                        usable_battery_level = lastthis.usable_battery_level
                        drange = lastprevmode.battery_range - battery_range
                        print("%s +%-16s Conditioned %2.0f%% %5.1fM or %5.1fM/d (to %3d%%)"%
                              (firstthismodetime.strftime('%Y-%m-%d %H:%M:%S'),
                               str(thistime-firstthismodetime),
                               lastprevmode.usable_battery_level - usable_battery_level,
                               drange,
                               drange / (((thistime-firstthismodetime).total_seconds()) / 86400.0),
                               usable_battery_level))


                    else:
                        print("Do not handle mode %s"%firstthismode.mode)
                    firstthismode = save
                    lastprevmode = lastthis
                break
            else:
                reallasttime = None
                firstthismode = save
                lastprevmode = save
            lastthis = save

            if args.verbose:
                outputit(this)

