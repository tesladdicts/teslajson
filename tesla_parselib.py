######################################################################
#
# Parse the tesla json records
#

import json
import copy

class tesla_record(object):
    """Abbreviated information about a specific record retrieved from a tesla"""
    def __init__(self, line, want_offline=False):
        """Create object from json text data from tesla_poller"""

        # self.jline set in new
        self.time = 			self.jline["retrevial_time"]
        self.vehicle_id = 		self.jline["vehicle_id"]
        self.state = 			self.jline["state"]
        self.car_locked = 		self._jget(["vehicle_state", "locaked"])
        self.odometer =			self._jget(["vehicle_state", "odometer"])
        self.is_user_present =		self._jget(["vehicle_state", "is_user_present"])
        self.charging_state =		self._jget(["charge_state",  "charging_state"])
        self.usable_battery_level =	self._jget(["charge_state",  "usable_battery_level"])
        self.charge_miles_added =	self._jget(["charge_state",  "charge_miles_added_rated"])
        self.charge_energy_added =	self._jget(["charge_state",  "charge_energy_added"])
        self.charge_current_request =	self._jget(["charge_state",  "charge_current_request"])
        self.charger_power =		self._jget(["charge_state",  "charger_power"])
        self.charge_rate =		self._jget(["charge_state",  "charge_rate"])
        self.charger_voltage =		self._jget(["charge_state",  "charger_voltage"])
        self.battery_range =		self._jget(["charge_state",  "battery_range"])
        self.est_battery_range =	self._jget(["charge_state",  "est_battery_range"])
        self.shift_state =		self._jget(["drive_state",   "shift_state"])
        self.speed =			self._jget(["drive_state",   "speed"])
        self.latitude =			self._jget(["drive_state",   "latitude"])
        self.longitude =		self._jget(["drive_state",   "longitude"])
        self.heading =			self._jget(["drive_state",   "heading"])
        self.gps_as_of =		self._jget(["drive_state",   "gps_as_of"])
        self.climate_on =		self._jget(["climate_state", "is_climate_on"])
        self.inside_temp =		self._jget(["climate_state", "inside_temp"])
        self.outside_temp =		self._jget(["climate_state", "outside_temp"])
        self.battery_heater =		self._jget(["climate_state", "battery_heater"])
        self.vin =			self.jline["vin"]
        self.display_name =		self.jline["display_name"]
        self.car_type =			self._jget(["vehicle_config", "car_type"])
        self.car_special_type =		self._jget(["vehicle_config", "car_special_type"])
        self.perf_config =		self._jget(["vehicle_config", "perf_config"])
        self.has_ludicrous_mode =	self._jget(["vehicle_config", "has_ludicrous_mode"])
        self.wheel_type =		self._jget(["vehicle_config", "wheel_type"])
        self.has_air_suspension =	self._jget(["vehicle_config", "has_air_suspension"])
        self.exterior_color =		self._jget(["vehicle_config", "exterior_color"])
        self.option_codes =		self._jget(["vehicle_config", "option_codes"])
        self.car_version =		self._jget(["vehicle_config", "car_version"])
        

        if self.charger_power > 0:
            self.mode = "Charging"
        elif self.shift_state and self.shift_state != "P":
            self.mode = "Driving"
        elif self.climate_on:
            self.mode = "Conditioning"
        elif self.charger_power is not None or self.odometer is not None:
            self.mode = "Standby"
        else:
            self.mode = "Polling"


    def __new__(cls, line=None, want_offline=False):
        """Return None if this isn't what we want"""

        if line is not None and (line.startswith("#") or len(line) < 10):
            return None

        instance = super(tesla_record, cls).__new__(cls)

        if line is None:
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
            if key not in info:
                return notfound
            info = info[key]
        return info
