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

    def sql_vehicle_insert_str(self):
        result = '({id},\'{vin}\''.format(id=self.vehicle_id, vin=self.vin)
	if self.display_name:
	    result = result + ",\'" + self.display_name + "\'"
	else:
	    result = result + ",NULL"
	if self.car_type:
	    result = result + ",\'" + self.car_type + "\'"
	else:
	    result = result + ",NULL"
	if self.car_special_type:
	    result = result + ",\'" + self.car_special_type + "\'"
	else:
	    result = result + ",NULL"
        if self.perf_config:
	    result = result + ",\'" + self.perf_config + "\'"
	else:
	    result = result + ",NULL"
	if self.has_ludicrous_mode is None:
	    result = result + ",NULL"
	else:
	    if self.has_ludicrous_mode:
	        result = result + ",TRUE"
	    else:
	        result = result + ",FALSE"
        if self.wheel_type:
	    result = result + ",\'" + self.wheel_type + "\'"
	else:
	    result = result + ",NULL"
	if self.has_air_suspension is None:
	    result = result + ",NULL"
        else:
	    if self.has_air_suspension:
                result = result + ",TRUE"
	    else:
	        result = result + ",FALSE"
	if self.exterior_color:
	    result = result + ",\'" + self.exterior_color + "\'"
        else:
	    result = result + ",NULL"
	if self.option_codes:
	    result = result + ",\'" + self.option_codes + "\'"
        else:
	    result = result + ",NULL"
        if self.car_version:
	    result = result + ",\'" + self.car_version + "\')"
	else:
	    result = result + ",NULL)"
        return result


    def sql_vehicle_update_str(self, current) :
	# construct a string with the columns that need to be updated ready for 
	# an SQL update command. We assume vin never changes, so we don't check it
        result = ""
        # check the display_name
        if current[2] != self.display_name:
	    result = " display_name = '" + self.display_name + "'"
	# check car_type
	if self.car_type is not None :
	    if current[3] != self.car_type:
		if( len(result) > 1 ):
		    result = result + ","
		result = result + " car_type = '" + self.car_type + "'"
	# check car_special_type
	if self.car_special_type is not None :
	    if current[4] != self.car_special_type:
		if( len(result) > 1 ):
		    result = result + ","
		result = result + " car_special_type = '" + self.car_special_type + "'"
	# check perf_config
	if self.perf_config is not None :
	    if current[5] != self.perf_config:
		if( len(result) > 1 ):
		    result = result + ","
		result = result + " perf_config = '" + self.perf_config + "'"
	# check has_ludicrous_mode
	if self.has_ludicrous_mode is not None :
	    if current[6] != self.has_ludicrous_mode:
	        if( len(result) > 1 ):
		    result = result + ","
		result = result + " has_ludicrous_mode = " + str(self.has_ludicrous_mode)
	# check wheel_type
	if self.wheel_type is not None :
	    if current[7] != self.wheel_type:
	        if( len(result) > 1 ):
		    result = result + ","
		result = result + " wheel_type = '" + self.wheel_type + "'"
	# check has_air_suspension
	if self.has_air_suspension is not None :
	    if current[8] != self.has_air_suspension:
	        if( len(result) > 1 ):
		    result = result + ","
		result = result + " has_air_suspension = " + str(self.has_air_suspension)
	# check exterior_color
	if self.exterior_color is not None :
	    if current[9] != self.exterior_color:
	        if( len(result) > 1 ):
		    result = result + ","
		result = result + " exterior_color = '" + self.exterior_color + "'"
	# check option_codes
	if self.option_codes is not None :
	    if current[10] != self.option_codes:
	        if( len(result) > 1 ):
		    result = result + ","
		result = result + " option_codes = '" + self.option_codes + "'"
	# check car_version
	if self.car_version is not None :
	    if current[11] != self.car_version:
		if( len(result) > 1 ):
		    result = result + ","
		result = result + " car_version = '" + self.car_version + "'"
	return result


    def sql_vehicle_status_insert_str(self):
        # make unixtime into date and time
        unix_timestamp = float(self.time)
        local_timezone = tzlocal.get_localzone()
        local_time = datetime.fromtimestamp(unix_timestamp, local_timezone)
        ts_str = local_time.strftime("%Y-%m-%d %H:%M:%S")
        result = '(\'{}\',{},\'{}\''.format(ts_str, self.vehicle_id, self.state, )
        if self.car_locked is None :
	    result = result + ",NULL"
	else :
	    result = result + ',{}'.format(str(self.car_locked))
        if self.odometer is None :
	    result = result + ",NULL"
	else :
	    result = result + ',{}'.format(str(self.odometer))
        if self.is_user_present is None :
	    result = result + ",NULL"
	else :
	    result = result + ',{}'.format(str(self.is_user_present))
        if self.shift_state is None :
	    result = result + ",NULL"
	else :
	    result = result + ',\'{}\''.format(self.shift_state)
#	speed SMALLINT DEFAULT NULL,
#	latitude DOUBLE PRECISION DEFAULT NULL,
#	longitude DOUBLE PRECISION DEFAULT NULL,
#	heading REAL DEFAULT NULL,
#	gps_as_of TIMESTAMP DEFAULT NULL,
#	charging_state VARCHAR(255) DEFAULT NULL,
#	battery_level SMALLINT DEFAULT NULL,
#	battery_range REAL DEFAULT NULL,
#	est_battery_range REAL DEFAULT NULL,
#	charge_rate REAL DEFAULT NULL,
#	miles_added REAL DEFAULT NULL,
#	energy_added REAL DEFAULT NULL,
#	charge_current_request REAL DEFAULT NULL,
#	charger_power REAL DEFAULT NULL,
#	charger_voltage REAL DEFAULT NULL,
#	inside_temp REAL DEFAULT NULL,
#	outside_temp REAL DEFAULT NULL,
#	climate_on BOOLEAN NOT NULL,
#	battery_heater BOOLEAN NOT NULL,
#	valet_mode BOOLEAN DEFAULT NULL
        result = result + ')'
        return result
      