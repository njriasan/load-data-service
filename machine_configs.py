import json

config_file = open('machines.json')
config_data = json.load(config_file)
controller_ip = config_data["controller-ip"]
controller_port = int (config_data["controller-port"])
upc_port = int (config_data["upc-port"])
querier_port = int (config_data["upc-port"])
tick_period = float (config_data["tick-period"])
pause_ticks = int (config_data["pause-ticks"])
kill_ticks = int (config_data["kill-ticks"])
swarm_port = int (config_data["swarm-port"])
machines_dict = config_data["machines"]
machines_list = []
for key, value in machines_dict.items ():
    machines_list.append ((key, float (value)))

register_user_endpoint = config_data["register_user_endpoint"]
find_endpoint = config_data["find_endpoint"]
find_one_endpoint = config_data["find_one_endpoint"]
delete_endpoint = config_data["delete_endpoint"]
count_endpoint = config_data["count_endpoint"]
distinct_endpoint = config_data["distinct_endpoint"]
insert_endpoint = config_data["insert_endpoint"]
insert_deprecated_endpoint = config_data["insert_deprecated_endpoint"]
update_endpoint = config_data["update_endpoint"]
replace_one_endpoint = config_data["replace_one_endpoint"]
update_deprecated_endpoint = config_data["update_deprecated_endpoint"]
service_endpoint = config_data["service_endpoint"]
cloud_key_endpoint = config_data["cloud_key_endpoint"]
cloud_aggregate_endpoint = config_data["cloud_aggregate_endpoint"]
query_endpoint = config_data["query_endpoint"]
privacy_budget_endpoint = config_data["privacy_budget_endpoint"]
certificate_bundle_path = config_data["certificate_bundle"]

config_file.close ()
