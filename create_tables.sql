CREATE TABLE vehicle (
	vehicle_id BIGINT NOT NULL,
	vin CHAR(17) NOT NULL,
	display_name VARCHAR(255) DEFAULT NULL,
	car_type VARCHAR(64) DEFAULT NULL,
	car_special_type VARCHAR(64) DEFAULT NULL,
	perf_config VARCHAR(64) DEFAULT NULL,
	has_ludicrous_mode BOOLEAN DEFAULT NULL,
	wheel_type VARCHAR(64) DEFAULT NULL,
	has_air_suspension BOOLEAN DEFAULT NULL,
	exterior_color VARCHAR(64) DEFAULT NULL,
	option_codes VARCHAR(1000) DEFAULT NULL,
	car_version VARCHAR(64) DEFAULT NULL,
	PRIMARY KEY (vehicle_id)
);

CREATE TABLE firmware (
	vehicle_id BIGINT REFERENCES vehicle(vehicle_id),
	car_version VARCHAR(64) DEFAULT NULL,
	timets TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (vehicle_id, car_version)
);

CREATE TABLE location (
	location_id BIGSERIAL PRIMARY KEY,
	latitude DOUBLE PRECISION NOT NULL,
	longitude DOUBLE PRECISION NOT NULL,
	latrad DOUBLE PRECISION NOT NULL,
	lonrad DOUBLE PRECISION NOT NULL,
	name VARCHAR(255) DEFAULT NULL,
	is_tesla_supercharger BOOLEAN DEFAULT NULL,
	is_charge_station BOOLEAN DEFAULT NULL,
	is_home BOOLEAN DEFAULT NULL,
	is_work BOOLEAN DEFAULT NULL
);

CREATE INDEX latidx ON location (latrad);
CREATE INDEX lonidx ON location (lonrad);

CREATE TABLE vehicle_status (
	timets TIMESTAMP WITH TIME ZONE NOT NULL,
	vehicle_id BIGINT REFERENCES vehicle(vehicle_id),
	state VARCHAR(16) DEFAULT NULL,
	car_locked BOOLEAN DEFAULT NULL,
	odometer REAL DEFAULT NULL,
	is_user_present BOOLEAN DEFAULT NULL,
	shift_state CHAR(1) DEFAULT NULL,
	speed SMALLINT DEFAULT NULL,
	latitude DOUBLE PRECISION DEFAULT NULL,
	longitude DOUBLE PRECISION DEFAULT NULL,
	heading REAL DEFAULT NULL,
	gps_as_of TIMESTAMP WITH TIME ZONE DEFAULT NULL,
	charging_state VARCHAR(255) DEFAULT NULL,
	usable_battery_level SMALLINT DEFAULT NULL,
	battery_range REAL DEFAULT NULL,
	est_battery_range REAL DEFAULT NULL,
	charge_rate REAL DEFAULT NULL,
	charge_miles_added REAL DEFAULT NULL,
	charge_energy_added REAL DEFAULT NULL,
	charge_current_request REAL DEFAULT NULL,
	charger_power REAL DEFAULT NULL,
	charger_voltage REAL DEFAULT NULL,
	inside_temp REAL DEFAULT NULL,
	outside_temp REAL DEFAULT NULL,
	climate_on BOOLEAN DEFAULT NULL,
	battery_heater BOOLEAN DEFAULT NULL,
	valet_mode BOOLEAN DEFAULT NULL,
	location_id BIGINT DEFAULT NULL REFERENCES location(location_id),
	PRIMARY KEY (timets,vehicle_id)
);
