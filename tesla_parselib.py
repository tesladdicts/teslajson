######################################################################
#
# Parse the tesla json records
#

import json
import copy
from datetime import datetime
import tzlocal


class tesla_record(object):
    """Abbreviated information about a specific record retrieved from a tesla"""
    def __init__(self, line, want_offline=False):
        """Create object from json text data from tesla_poller"""

        # self.jline set in new
        self.time = 			self.jline["retrevial_time"]
        self.vehicle_id = 		self.jline["vehicle_id"]
        self.state = 			self.jline["state"]
        self.car_locked = 		self._jget(["vehicle_state", "locked"])
        self.odometer =			self._jget(["vehicle_state", "odometer"])
        self.is_user_present =		self._jget(["vehicle_state", "is_user_present"])
        self.valet_mode =		self._jget(["vehicle_state", "valet_mode"])
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
        self.option_codes =		self.jline["option_codes"]
        self.car_version =		self._jget(["vehicle_state", "car_version"])
        

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


    def sql_vehicle_insert_dict(self):
	# construct a dictionary with keys and values to insert, to be used in a psycopg2 
	# vehicle_id and vin need to exist so we just add them
	result = {}
        result["vehicle_id"] = self.vehicle_id
        result["vin"] = self.vin
	if self.display_name is not None:
	    result["display_name"] = self.display_name
	if self.car_type is not None:
	    result["car_type"] = self.car_type
	if self.car_special_type is not None:
	    result["car_special_type"] = self.car_special_type
        if self.perf_config is not None:
	    result["perf_config"] = self.perf_config
	if self.has_ludicrous_mode is not None:
	    result["has_ludicrous_mode"] = self.has_ludicrous_mode
        if self.wheel_type is not None:
	    result["wheel_type"] = self.wheel_type
	if self.has_air_suspension is not None:
	    result["has_air_suspension"] = self.has_air_suspension
	if self.exterior_color is not None:
	    result["exterior_color"] = self.exterior_color
	if self.option_codes is not None:
	    result["option_codes"] = self.option_codes
        if self.car_version is not None:
	    result["car_version"] = self.car_version
        return result


    def sql_vehicle_update_dict(self, current) :
	# construct a dictionary with keys and values to change, to be used in a psycopg2 
	# update execute command. We assume vin never changes, so we don't check it
        result = {}
        # check the display_name
        if current[2] != self.display_name:
	    result["display_name"]= self.display_name
	# check car_type
	if self.car_type is not None :
	    if current[3] != self.car_type:
		result["car_type"] = self.car_type
	# check car_special_type
	if self.car_special_type is not None :
	    if current[4] != self.car_special_type:
		result["car_special_type"] = self.car_special_type
	# check perf_config
	if self.perf_config is not None :
	    if current[5] != self.perf_config:
		result["perf_config"] = self.perf_config
	# check has_ludicrous_mode
	if self.has_ludicrous_mode is not None :
	    if current[6] != self.has_ludicrous_mode:
		result["has_ludicrous_mode"] = self.has_ludicrous_mode
	# check wheel_type
	if self.wheel_type is not None :
	    if current[7] != self.wheel_type:
		result["wheel_type"] = self.wheel_type
	# check has_air_suspension
	if self.has_air_suspension is not None :
	    if current[8] != self.has_air_suspension:
		result["has_air_suspension"] = self.has_air_suspension
	# check exterior_color
	if self.exterior_color is not None :
	    if current[9] != self.exterior_color:
		result["exterior_color"] = self.exterior_color
	# check option_codes
	if self.option_codes is not None :
	    if current[10] != self.option_codes:
		result["option_codes"] = self.option_codes
	# check car_version
	if self.car_version is not None :
	    if current[11] != self.car_version:
		result["car_version"] = self.car_version
	return result


    def sql_vehicle_status_insert_dict(self):
        result = {}
        # make unixtime into date and time
        unix_timestamp = float(self.time)
        local_timezone = tzlocal.get_localzone()
        local_time = datetime.fromtimestamp(unix_timestamp, local_timezone)
        ts_str = local_time.strftime("%Y-%m-%d %H:%M:%S")
        result["ts"] = ts_str
        result["vehicle_id"] = self.vehicle_id
        result["state"] = self.state
        if self.car_locked is not None :
	    result["car_locked"] = self.car_locked
        if self.odometer is not None :
	    result["odometer"] = self.odometer
        if self.is_user_present is not None :
	    result["is_user_present"] = self.is_user_present
        if self.shift_state is not None :
	    result["shift_state"] = self.shift_state
        if self.speed is not None :
	    result["speed"] = self.speed
        if self.latitude is not None :
	    result["latitude"] = self.latitude
        if self.longitude is not None :
	    result["longitude"] = self.longitude
        if self.heading is not None :
	    result["heading"] = self.heading
        if self.gps_as_of is not None :
            # make gps_as_of unixtime into date and time
            unix_timestamp = float(self.gps_as_of)
            local_timezone = tzlocal.get_localzone()
            local_time = datetime.fromtimestamp(unix_timestamp, local_timezone)
            gps_str = local_time.strftime("%Y-%m-%d %H:%M:%S")
            result["gps_as_of"] = gps_str
        if self.charging_state is not None :
	    result["charging_state"] = self.charging_state
        if self.usable_battery_level is not None :
	    result["battery_level"] = self.usable_battery_level
        if self.battery_range is not None :
	    result["battery_range"] = self.battery_range
        if self.est_battery_range is not None :
	    result["est_battery_range"] = self.est_battery_range
        if self.charge_rate is not None :
	    result["charge_rate"] = self.charge_rate
        if self.charge_miles_added is not None :
	    result["miles_added"] = self.charge_miles_added
        if self.charge_energy_added is not None :
	    result["energy_added"] = self.charge_energy_added
        if self.charge_current_request is not None :
	    result["charge_current_request"] = self.charge_current_request
        if self.charger_power is not None :
	    result["charger_power"] = self.charger_power
        if self.charger_voltage is not None :
	    result["charger_voltage"] = self.charger_voltage
        if self.inside_temp is not None :
	    result["inside_temp"] = self.inside_temp
        if self.outside_temp is not None :
	    result["outside_temp"] = self.outside_temp
        if self.climate_on is not None :
	    result["climate_on"] = self.climate_on
        if self.battery_heater is not None :
	    result["battery_heater"] = self.battery_heater
        if self.valet_mode is not None :
	    result["valet_mode"] = self.valet_mode
        return result
      