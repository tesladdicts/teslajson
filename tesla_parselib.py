######################################################################
#
# Parse the tesla json records
#

import json
import copy
from datetime import datetime
import pytz


class tesla_record(object):
    """Abbreviated information about a specific record retrieved from a tesla"""
    def __init__(self, line=None, tdata=None, want_offline=False):
        """Create object from json text data from tesla_poller"""

        if self.jline:
            # self.jline set in new
            self.timets =                   self.jline["retrevial_time"]
            self.vehicle_id =               self.jline["vehicle_id"]
            self.state =                    self.jline["state"]
            self.car_locked =               self._jget(["vehicle_state", "locked"])
            self.odometer =                 self._jget(["vehicle_state", "odometer"])
            self.is_user_present =          self._jget(["vehicle_state", "is_user_present"])
            self.valet_mode =               self._jget(["vehicle_state", "valet_mode"])
            self.charging_state =           self._jget(["charge_state",  "charging_state"])
            self.usable_battery_level =     self._jget(["charge_state",  "usable_battery_level"])
            self.charge_miles_added =       self._jget(["charge_state",  "charge_miles_added_rated"])
            self.charge_energy_added =      self._jget(["charge_state",  "charge_energy_added"])
            self.charge_current_request =   self._jget(["charge_state",  "charge_current_request"])
            self.charger_power =            self._jget(["charge_state",  "charger_power"])
            self.charge_rate =              self._jget(["charge_state",  "charge_rate"])
            self.charger_voltage =          self._jget(["charge_state",  "charger_voltage"])
            self.battery_range =            self._jget(["charge_state",  "battery_range"])
            self.est_battery_range =        self._jget(["charge_state",  "est_battery_range"])
            self.shift_state =              self._jget(["drive_state",   "shift_state"])
            self.speed =                    self._jget(["drive_state",   "speed"])
            self.latitude =                 self._jget(["drive_state",   "latitude"])
            self.longitude =                self._jget(["drive_state",   "longitude"])
            self.heading =                  self._jget(["drive_state",   "heading"])
            self.gps_as_of =                self._jget(["drive_state",   "gps_as_of"])
            self.climate_on =               self._jget(["climate_state", "is_climate_on"])
            self.inside_temp =              self._jget(["climate_state", "inside_temp"])
            self.outside_temp =             self._jget(["climate_state", "outside_temp"])
            self.battery_heater =           self._jget(["climate_state", "battery_heater"])
            self.vin =                      self.jline["vin"]
            self.display_name =             self.jline["display_name"]
            self.car_type =                 self._jget(["vehicle_config", "car_type"])
            self.car_special_type =         self._jget(["vehicle_config", "car_special_type"])
            self.perf_config =              self._jget(["vehicle_config", "perf_config"])
            self.has_ludicrous_mode =       self._jget(["vehicle_config", "has_ludicrous_mode"])
            self.wheel_type =               self._jget(["vehicle_config", "wheel_type"])
            self.has_air_suspension =       self._jget(["vehicle_config", "has_air_suspension"])
            self.exterior_color =           self._jget(["vehicle_config", "exterior_color"])
            self.option_codes =             self.jline["option_codes"]
            self.car_version =              self._jget(["vehicle_state", "car_version"])

        if tdata:
            for k in ('timets', 'vehicle_id', 'state', 'car_locked', 'odometer', 'is_user_present', 'valet_mode', 'charging_state', 'usable_battery_level', 'charge_miles_added', 'charge_energy_added', 'charge_current_request', 'charger_power', 'charge_rate', 'charger_voltage', 'battery_range', 'est_battery_range', 'shift_state', 'speed', 'latitude', 'longitude', 'heading', 'gps_as_of', 'climate_on', 'inside_temp', 'outside_temp', 'battery_heater', 'vin', 'display_name', 'car_type', 'car_special_type', 'perf_config', 'has_ludicrous_mode', 'wheel_type', 'has_air_suspension', 'exterior_color', 'option_codes', 'car_version'):
                if k in tdata and tdata[k] is not None:
                    if k in ('timets','gps_as_of'):
                        setattr(self, k, float(tdata[k].strftime('%s')))
                    else:
                        setattr(self, k, tdata[k])
                else:
                    setattr(self, k, None)

        if self.charger_power is not None and self.charger_power > 0:
            self.mode = "Charging"
        elif self.shift_state is not None and self.shift_state != "P":
            self.mode = "Driving"
        elif self.climate_on:
            self.mode = "Conditioning"
        elif self.charger_power is not None or self.odometer is not None:
            self.mode = "Standby"
        else:
            self.mode = "Polling"



    def __new__(cls, line=None, tdata=None, want_offline=False):
        """Return None if this isn't what we want"""

        if line is not None and (line.startswith("#") or len(line) < 10):
            return None

        instance = super(tesla_record, cls).__new__(cls)

        if line is None:
            instance.jline = None
            return instance

        try:
            instance.jline = json.loads(line)
        except Exception as e:
            return None

        if "retrevial_time" not in instance.jline:
            return None

        if instance.jline["state"] != "online" and not want_offline:
            return None

        return instance



    def __add__(self, b):
        result = copy.copy(self)
        for attr in b.__dict__:
            v = getattr(b, attr)
            if v:
                setattr(result, attr, v)
        return result



    def _jget(self, tree, notfound=None):
        info = self.jline
        for key in tree:
            if key not in info or info[key] is None:
                return notfound
            info = info[key]
        return info



    def sql_vehicle_insert_dict(self):

        """Construct a dictionary with keys and values to insert, to be used
        in a psycopg2 vehicle_id and vin need to exist so we just add them"""

        result = {}

        for memid in ("vehicle_id", "vin", "display_name", "car_type", "car_special_type", "perf_config", "has_ludicrous_mode", "wheel_type", "has_air_suspension", "exterior_color", "option_codes", "car_version"):
            if getattr(self, memid) is not None:
                result[memid] = getattr(self, memid)

        return result



    def sql_vehicle_update_dict(self, current) :
        """Construct a dictionary with keys and values to change, to be used in a psycopg2
        update execute command. We assume vin never changes, so we don't check it"""
        result = {}

        for memid in ("display_name", "car_type", "car_special_type", "perf_config", "has_ludicrous_mode", "wheel_type", "has_air_suspension", "exterior_color", "option_codes", "car_version"):
            if getattr(self, memid) is not None:
                if current.get(memid, None) != getattr(self, memid):
                    result[memid] = getattr(self, memid)
        return result



    def sql_vehicle_status_insert_dict(self):
        """Construct a dictionary to insert data into vehicle_status"""

        result = {}

        for memid in ("vehicle_id", "state", "car_locked", "odometer", "is_user_present", "shift_state", "speed", "latitude", "longitude", "heading", "charging_state", "usable_battery_level", "battery_range", "est_battery_range", "charge_rate", "charge_miles_added", "charge_energy_added", "charge_current_request", "charger_power", "charger_voltage", "inside_temp", "outside_temp", "climate_on", "battery_heater", "valet_mode"):
            if getattr(self, memid) is not None:
                result[memid] = getattr(self, memid)

        result["timets"] = datetime.fromtimestamp(float(self.timets), pytz.timezone("UTC")).isoformat()

        if self.gps_as_of is not None :
            result["gps_as_of"] = datetime.fromtimestamp(float(self.gps_as_of), pytz.timezone("UTC")).isoformat()
        return result
