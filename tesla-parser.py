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



lastmode = None
save = None

for fname in args.files:
    with openfile(fname, args) as R:
        while True:
            line = R.readline()
            if not line:
                break
            this = tesla_parselib.tesla_record(line)

            if not this:
                continue

            if save:
                save = save + this
            else:
                save = this

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


            while lastmode and not args.nosummary:
                if lastmode.mode != this.mode:
                    lastmodetime = datetime.datetime.fromtimestamp(lastmode.time)
                    thistime = datetime.datetime.fromtimestamp(save.time)
                    if lastmode.mode == "Charging":
                        battery_range = save.battery_range if save.battery_range > lastthis.battery_range else lastthis.battery_range
                        usable_battery_level = save.usable_battery_level if save.usable_battery_level > lastthis.usable_battery_level else lastthis.usable_battery_level
                        dblevel = usable_battery_level - lastmode.usable_battery_level

                        print("%s +%-16s Charged   %3d%% %5.2fkW %5.1fM (%3dmph, %4.1fkW %5.1fM max)"%
                              (lastmodetime.strftime('%Y-%m-%d %H:%M:%S'),
                               str(thistime-lastmodetime),
                               dblevel,
                               save.charge_energy_added,
                               battery_range - lastmode.battery_range,
                               ((battery_range - lastmode.battery_range)*3600.0 /
                                (thistime-lastmodetime).total_seconds()),
                               (save.charge_energy_added * 100.0 /
                                (dblevel)) if dblevel > 0 else -0,
                               battery_range * 100.0 / save.usable_battery_level))
                    elif lastmode.mode == "Driving":
                        if not this.odometer:
                            break
                        battery_range = save.battery_range if save.battery_range < lastthis.battery_range else lastthis.battery_range
                        usable_battery_level = save.usable_battery_level if save.usable_battery_level < lastthis.usable_battery_level else lastthis.usable_battery_level
                        dodo = save.odometer - lastmode.odometer
                        drange = lastmode.battery_range - battery_range

                        if dodo > -1:
                            print("%s +%-16s Drove  %6.2fM at cost of %4.1f%% %5.1fM at %5.1f%% efficiency"%
                                  (lastmodetime.strftime('%Y-%m-%d %H:%M:%S'),
                                   str(thistime-lastmodetime),
                                   dodo,
                                   lastmode.usable_battery_level - usable_battery_level,
                                   drange,
                                   dodo * 100.0 / drange if drange > 0 else -0))
                    elif lastmode.mode == "Standby":
                        battery_range = save.battery_range if save.battery_range < lastthis.battery_range else lastthis.battery_range
                        usable_battery_level = save.usable_battery_level if save.usable_battery_level < lastthis.usable_battery_level else lastthis.usable_battery_level
                        drange = lastmode.battery_range - battery_range
                        print("%s +%-16s Sat&Lost %4.1f%% %5.1fM or %5.1fM/d"%
                              (lastmodetime.strftime('%Y-%m-%d %H:%M:%S'),
                               str(thistime-lastmodetime),
                               lastmode.usable_battery_level - usable_battery_level,
                               drange,
                               drange / (((thistime-lastmodetime).total_seconds()) / 86400.0)))


                    else:
                        print("Do not handle mode %s"%lastmode.mode)
                    lastmode = save
                break
            else:
                lastmode = save
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
