#!/usr/bin/python
#
# Print the data stored by tesla_poller
#

import argparse
import datetime
from datetime import datetime
import subprocess
import tesla_parselib
import json
import psycopg2
import psycopg2.extras
import sys
import pytz

# Update if you cannot find this
from psycopg2.extensions import AsIs

parser = argparse.ArgumentParser()
parser.add_argument('--verbose', '-v', action='count', help='Increasing levels of verbosity')
parser.add_argument('--nosummary', action='store_true', help='Do not print summary information')
parser.add_argument('--follow', '-f', type=str, help='Follow this specific file')
parser.add_argument('--numlines', '-n', type=str, help='Handle these number of lines')
parser.add_argument('--outdir', default=None, help='Convert input files into daily output files')
parser.add_argument('--dbconfig', type=str, help='Insert records in database using this config file')
parser.add_argument('files', nargs='*')
args = parser.parse_args()

if args.verbose is None:
    args.verbose = 0

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
    # open the database
    try:
        dbconn = psycopg2.connect(**dbinfo)
        cursor = dbconn.cursor()
        cursor.execute("SELECT version();")
        record = cursor.fetchone()
        if args.verbose:
            print('Connected to {}\n'.format(str(record[0])))
        cursor.close()
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
          (datetime.fromtimestamp(this.timets).strftime('%Y-%m-%d %H:%M:%S'),
           this.mode,
           "%.2f"%this.odometer if this.odometer else "",
           str(this.speed or ""),
           bat,
           rate,
           add))



def analyzer(this, firstthismode, lastprevmode, save, lastthis, reallasttime):
    if this.mode == "Polling":
        reallasttime = this.timets
        if args.verbose > 1:
            outputit(this)
        return (firstthismode, lastprevmode, save, lastthis, reallasttime)

    if save:
        save = save + this
    else:
        save = this
        prev = this

    # analyze data and provide a summary
    while firstthismode and not args.nosummary:
        if firstthismode.mode != this.mode:
            if reallasttime:
                this.timets = reallasttime
                reallasttime = None

            firstthismodetime = datetime.fromtimestamp(firstthismode.timets)
            thistime = datetime.fromtimestamp(save.timets)
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
                speeds = sorted(firstthismode.speeds)
                if not speeds:
                    speeds.append(0)
                qspeeds = map(lambda x: str(x), [speeds[int((len(speeds)-1)/4)],speeds[int((len(speeds)-1)/2)],speeds[int(3*(len(speeds)-1)/4)],speeds[len(speeds)-1]])
                dhours = ((thistime-firstthismodetime).total_seconds()/3600.0)
                if dhours < .0001:
                    dhours = .0001

                if dodo > -1 and dodo != 0:
                    print("%s +%-16s Drove  %6.2fM at cost of %2.0f%% %5.1fM at %5.1f%% efficiency; %dWhpm mph:%.0f %s"%
                          (firstthismodetime.strftime('%Y-%m-%d %H:%M:%S'),
                           str(thistime-firstthismodetime),
                           dodo,
                           lastprevmode.usable_battery_level - usable_battery_level,
                           drange,
                           dodo * 100.0 / drange if drange > 0 else -0,
                           78200*(lastprevmode.usable_battery_level - usable_battery_level)/100/dodo,
                           dodo/dhours,
                           '/'.join(qspeeds)
                          ))
                firstthismode.speeds = []
                save.speeds = []
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
    if firstthismode.mode == "Driving":
        if not hasattr(firstthismode, 'speeds'):
            firstthismode.speeds = []
        if this.speed > 0:
            firstthismode.speeds.append(this.speed)
    lastthis = save

    if args.verbose:
        outputit(this)

    return (firstthismode, lastprevmode, save, lastthis, reallasttime)



firstthismode = None
lastprevmode = None
save = None
lastthis = None
reallasttime = None

if args.dbconfig and not args.files:
    cursor = dbconn.cursor(cursor_factory = psycopg2.extras.DictCursor)
    query = 'SELECT * FROM vehicle;'
    cursor.execute(query)
    for vres in cursor.fetchall():
        query = 'SELECT * FROM vehicle_status where vehicle_id=%s order by timets;'
        cursor.execute(query, (vres['vehicle_id'],))
        for res in cursor.fetchall():
            ares = dict(vres)
            ares.update(res)
            this = tesla_parselib.tesla_record(line=None, tdata=ares, want_offline=(args.verbose>2))
            (firstthismode, lastprevmode, save, lastthis, reallasttime) = analyzer(this, firstthismode, lastprevmode, save, lastthis, reallasttime)
    sys.exit(0)

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
                try:
                    cursor = dbconn.cursor(cursor_factory = psycopg2.extras.DictCursor)
                    query = 'SELECT * FROM vehicle WHERE vehicle_id=%s'
                    cursor.execute(query, (this.vehicle_id,))
                except (Exception, psycopg2.Error) as error :
                    if(dbconn):
                        print(error)
                        print("Failed to query vehicle table, cannot continue")
                        exit()
                if cursor.rowcount<1:
                    # this is the first time we've seen this car, add it
                    insert_str = "INSERT INTO vehicle (%s) VALUES %s"
                    insertargs = this.sql_vehicle_insert_dict()
                    columns = insertargs.keys()
                    values = insertargs.values()
                    try:
                        cursor.execute(insert_str, (AsIs(','.join(columns)), tuple(values)))
                    except (Exception, psycopg2.Error) as error :
                        if args.verbose>0:
                            print(error)
                        print("Failed to insert record into vehicle table, skipping status")
                        dbconn.rollback()
                        cursor.close()
                        continue
                    else:
                        dbconn.commit()
                    # add also the firmware 
                    fwargs = {}
                    insert_str = "INSERT INTO firmware (%s) VALUES %s"
                    fwargs["vehicle_id"] = this.vehicle_id
                    fwargs["car_version"] = this.car_version
                    fwargs['timets'] = datetime.fromtimestamp(float(this.timets),pytz.timezone("UTC")).isoformat()
                    columns = fwargs.keys()
                    values = fwargs.values()
                    try:
                        cursor.execute(insert_str, (AsIs(','.join(columns)), tuple(values)))
                    except psycopg2.Error as error :
                        if error.diag.sqlstate == '23505':
                            dbconn.rollback()
                else:
                    # we've already got this car, check if anything changed and update
                    res = cursor.fetchone()
                    # check if we need to update anything and get the string for the update
                    updateargs = this.sql_vehicle_update_dict(res)
                    # update the row if needed
                    if len(updateargs) > 0:
		        if len(updateargs) == 1:
		            query = 'UPDATE vehicle SET %s = %s WHERE vehicle_id = %s'
                        else:
                            query = "UPDATE vehicle SET (%s) = %s WHERE vehicle_id = %s"
                        vals = (AsIs(','.join(updateargs.keys())), tuple(updateargs.values()), this.vehicle_id)
                        try:
                            cursor.execute(query, vals)
                        except (Exception, psycopg2.Error) as error :
                            dbconn.rollback()
                            if args.verbose>0:
                                print(error)
                            print("Failed to update record in vehicle table")
                        else:
                            dbconn.commit()
                        # check for version updates
                        if updateargs['car_version'] is not None:
                            # log the version change
                            fwargs = {}
                            insert_str = "INSERT INTO firmware (%s) VALUES %s"
                            fwargs['vehicle_id'] = this.vehicle_id
                            fwargs['car_version'] = this.car_version
                            fwargs['timets'] = datetime.fromtimestamp(float(this.timets),pytz.timezone("UTC")).isoformat()
                            columns = fwargs.keys()
                            values = fwargs.values()
                            try:
                                cursor.execute(insert_str, (AsIs(','.join(columns)), tuple(values)))
                            except psycopg2.Error as error :
                                if error.diag.sqlstate == '23505':
                                    dbconn.rollback()
                # close cursor and open a new one to clear any possible error
                try:
                    cursor.close()
                except (Exception, psycopg2.Error) as error :
                    print(error)
                    print("Trouble with the database connection, cannot continue")
                    exit()
                cursor = dbconn.cursor()
                # add a new vehicle_status row
                # if the user wants verbosity we will expose duplicate key errors
                # if no verbosity is requested we silently skip inserts with duplicate key
                insert_str = "INSERT INTO vehicle_status (%s) VALUES %s"
                insertargs = this.sql_vehicle_status_insert_dict()
                columns = insertargs.keys()
                values = insertargs.values()
                try:
                    cursor.execute(insert_str, (AsIs(','.join(columns)), tuple(values)))
                except psycopg2.Error as error :
                        if error.diag.sqlstate == '23505':
                            dbconn.rollback()
                            if len(insertargs.keys()) > 3:
                                update_str = "UPDATE vehicle_status SET (%s) = %s WHERE vehicle_id = %s AND timets = %s"
                                updateargs = dict(insertargs)
                                del(updateargs['vehicle_id'])
                                del(updateargs['timets'])
                                columns = updateargs.keys()
                                values = updateargs.values()
                                cursor.execute(update_str, (AsIs(','.join(columns)), tuple(values), insertargs['vehicle_id'], insertargs['timets']))
                            else:
                                # Trivial update
                                pass
#                                print("Did not insert record into vehicle_status: duplicate timestamp and short: %s"%str(insertargs))
#                                if args.verbose>1:
#                                    print('vehicle: {} timestamp: {}'.format(insertargs['vehicle_id'],insertargs['timets']))
                        else:
			    if args.verbose>0:
                                print(error.diag.sqlstate)
                            print("Error: failed to insert record into vehicle_status: %s"%str(error))
                            dbconn.rollback()
                except Exception as error :
                    print("Error: failed to insert record into vehicle_status: %s"%str(error))
                    dbconn.rollback()
                else:
                    dbconn.commit()
                # close this cursor, will open a new one in next iteration
                cursor.close()
                # as we are inserting data into the database we do nothing else with this record
                continue

            # output data to file in outdir
            if args.outdir:
                output_maintenance(this.timets)
                X.write(line)


            (firstthismode, lastprevmode, save, lastthis, reallasttime) = analyzer(this, firstthismode, lastprevmode, save, lastthis, reallasttime)
