#!/usr/bin/python
#
# Print the data stored by telsa_poller
#

import argparse
import datetime
import subprocess
import tesla_parselib

parser = argparse.ArgumentParser()
parser.add_argument('--verbose', '-v', action='count', help='Increasing levels of verbosity')
parser.add_argument('--nosummary', action='store_true', help='Do not print summary information')
parser.add_argument('--follow', '-f', type=str, help='Follow this specific file')
parser.add_argument('--numlines', '-n', type=str, help='Handle these number of lines')
parser.add_argument('--outdir', default=None, help='Convert input files into daily output files')
parser.add_argument('files', nargs='*')
args = parser.parse_args()

if not args.numlines:
    args.numlines = "10"

if args.follow:
    args.files.append(None)

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


firstthismode = None
lastprevmode = None
save = None
lastthis = None
reallasttime = None

for fname in args.files:
    with openfile(fname, args) as R:
        while True:
            line = R.readline()
            if not line:
                break
            this = tesla_parselib.tesla_record(line)

            if not this:
                continue

            if args.outdir:
                output_maintenance(this.time)
                X.write(line)

            if this.mode == "Polling":
                reallasttime = this.time
                continue

            if save:
                save = save + this
            else:
                save = this
                prev = this

            if this.usable_battery_level:
                bat="%3d%%/%.2fM"%(this.usable_battery_level,this.battery_range)
            else:
                bat=""

            if this.charge_energy_added:
                add = "%5.2f/%.1fM"%(this.charge_energy_added, this.charge_miles_added)
            else:
                add = ""

            if this.charge_rate:
                rate = "%dkW/%dM"%(this.charger_power,this.charge_rate)
            else:
                rate=""


            while firstthismode and not args.nosummary:
                if firstthismode.mode != this.mode:

                    if reallasttime:
                        this.time = reallasttime
                        reallasttime = None

                    firstthismodetime = datetime.datetime.fromtimestamp(firstthismode.time)
                    thistime = datetime.datetime.fromtimestamp(save.time)
                    if firstthismode.mode == "Charging":
                        battery_range = save.battery_range if save.battery_range > lastthis.battery_range else lastthis.battery_range
                        usable_battery_level = save.usable_battery_level if save.usable_battery_level > lastthis.usable_battery_level else lastthis.usable_battery_level
                        dblevel = usable_battery_level - lastprevmode.usable_battery_level

                        print("%s +%-16s Charged   %3d%% %5.2fkW %5.1fM (%3dmph, %4.1fkW %5.1fM max)"%
                              (firstthismodetime.strftime('%Y-%m-%d %H:%M:%S'),
                               str(thistime-firstthismodetime),
                               dblevel,
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
                            print("%s +%-16s Drove  %6.2fM at cost of %4.1f%% %5.1fM at %5.1f%% efficiency"%
                                  (firstthismodetime.strftime('%Y-%m-%d %H:%M:%S'),
                                   str(thistime-firstthismodetime),
                                   dodo,
                                   lastprevmode.usable_battery_level - usable_battery_level,
                                   drange,
                                   dodo * 100.0 / drange if drange > 0 else -0))
                    elif firstthismode.mode == "Standby":
                        battery_range = save.battery_range if save.battery_range < lastthis.battery_range else lastthis.battery_range
                        usable_battery_level = save.usable_battery_level if save.usable_battery_level < lastthis.usable_battery_level else lastthis.usable_battery_level
                        drange = lastprevmode.battery_range - battery_range
                        print("%s +%-16s Sat&Lost %4.1f%% %5.1fM or %5.1fM/d"%
                              (firstthismodetime.strftime('%Y-%m-%d %H:%M:%S'),
                               str(thistime-firstthismodetime),
                               lastprevmode.usable_battery_level - usable_battery_level,
                               drange,
                               drange / (((thistime-firstthismodetime).total_seconds()) / 86400.0)))


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
                print("%s %-8s odo=%-7s spd=%-3s bat=%-12s chg@%-12s add=%s"%
                      (datetime.datetime.fromtimestamp(this.time).strftime('%Y-%m-%d %H:%M:%S'),
                       this.mode,
                       "%.2f"%this.odometer if this.odometer else "",
                       str(this.speed or ""),
                       bat,
                       rate,
                       add))
