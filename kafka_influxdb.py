from collections import defaultdict
import argparse
import yaml
import logging
import importlib
from reader import kafka_reader
from writer import influxdb_writer

class KafkaInfluxDB(object):
	def __init__(self, reader, encoder, writer, config):
		""" Setup """
		self.config = config
		self.reader = reader
		self.encoder = encoder
		self.writer = writer
		self.buffer = []

	def consume(self):
		""" Run loop. Consume messages from reader, convert it to the output format and write with writer """
		logging.info("Listening for messages on kafka topic ", self.config.kafka_topic)
		try:
			for index, raw_message in enumerate(self.reader.read(), 1):
				self.buffer.append(self.encoder.encode(raw_message))
				if index % self.config.buffer_size == 0:
					self.flush()
		except KeyboardInterrupt:
			logging.info("Shutdown")

	def flush(self):
		""" Flush values with writer """
		try:
			self.writer.write(self.buffer)
			self.buffer = []
		except Exception, e:
			logging.warning(e)

	def get_config(self):
		return self.config

def main():
	config = parse_args()
	if config.verbose:
		logging.getLogger().setLevel(logging.DEBUG)

	if config.configfile:
		logging.debug("Reading config from ", config.configfile)
		values = parse_configfile(config.configfile)
		overwrite_config_values(values)
	else:
		logging.info("Using default configuration")

	reader = kafka_reader.KafkaReader(config.kafka_host,
									config.kafka_port,
									config.kafka_group,
									config.kafka_topic)

	encoder = load_encoder(config.encoder)
	writer = influxdb_writer.InfluxDBWriter(config.influxdb_host,
									config.influxdb_port,
									config.influxdb_user,
									config.influxdb_password,
									config.influxdb_dbname,
									config.influxdb_retention_policy,
									config.influxdb_time_precision)

	client = KafkaInfluxDB(reader, encoder, writer, config)
	client.consume()

def load_encoder(encoder_name):
	"""
	Creates an instance of the given encoder.
	An encoder converts a message from one format to another
	"""
	encoder_module = importlib.import_module("encoder." + encoder_name)
	return getattr(encoder_module, "Encoder")

def parse_configfile(configfile):
	""" Read settings from file """
	with open(configfile) as f:
		try:
			return yaml.safe_load(f)
		except Exception, e :
			logging.fatal("Could not load default config file: ", e)
			exit(-1)

def overwrite_config_values(config, values, prefix = ""):
	""" Overwrite default config with custom values """
	for key, value in values.iteritems() :
		if type(value) == type(dict()):
			overwrite_config_values(config, value, "%s_" % key)
		elif value != u'':
			setattr(config, "%s%s" % (prefix, key), value)

def parse_args():
	parser = argparse.ArgumentParser(description='A Kafka consumer for InfluxDB', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
	parser.add_argument('--kafka_host', type=str, default='localhost', required=False, help="Hostname or IP of Kafka message broker")
	parser.add_argument('--kafka_port', type=int, default=9092, required=False, help="Port of Kafka message broker")
	parser.add_argument('--kafka_topic', type=str, default='test', required=False, help="Topic for metrics")
	parser.add_argument('--kafka_group', type=str, default='my_group', required=False, help="Kafka consumer group")
	parser.add_argument('--influxdb_host', type=str, default='localhost', required=False, help="InfluxDB hostname or IP")
	parser.add_argument('--influxdb_port', type=int, default=8086, required=False, help="InfluxDB API port")
	parser.add_argument('--influxdb_user', type=str, default='root', required=False, help="InfluxDB username")
	parser.add_argument('--influxdb_password', type=str, default='root', required=False, help="InfluxDB password")
	parser.add_argument('--influxdb_dbname', type=str, default='kafka', required=False, help="InfluXDB database to write metrics into")
	parser.add_argument('--influxdb_retention_policy', type=str, default=None, required=False, help="Retention policy for incoming metrics")
	parser.add_argument('--influxdb_time_precision', type=str, default="s", required=False, help="Precision of incoming metrics. Can be one of 's', 'm', 'ms', 'u'")
	parser.add_argument('--encoder', type=str, default='collectd_graphite_encoder', required=False, help="Input encoder which converts an incoming message to dictionary")
	parser.add_argument('--buffer_size', type=int, default=1000, required=False, help="Maximum number of messages that will be collected before flushing to the backend")
	parser.add_argument('-c', '--configfile', type=str, default=None, required=False, help="Configfile path")
	parser.add_argument('-v', '--verbose', action="store_true", help="Show info and debug messages while running")
	return parser.parse_args()

if __name__ == '__main__'	:
	main()
