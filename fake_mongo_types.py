import pymongo
import requests
import socket
import json
import bson

import urllib3
urllib3.disable_warnings(urllib3.exceptions.SecurityWarning)

from machine_configs import find_one_endpoint, find_endpoint, count_endpoint, distinct_endpoint, insert_endpoint, delete_endpoint, update_endpoint, insert_deprecated_endpoint, update_deprecated_endpoint, replace_one_endpoint, controller_ip, controller_port, service_endpoint, privacy_budget_endpoint


def convert_string_to_objectid(dict_or_list_or_item):
    if isinstance(dict_or_list_or_item, dict):
        for key, value in dict_or_list_or_item.copy().items():
            # Agressively assume anything that can be an ObjectId is
            # This may cause us problems later
            if bson.ObjectId.is_valid(value):
                dict_or_list_or_item[key] = bson.ObjectId(value)
            else:
                convert_string_to_objectid(value)
    elif isinstance(dict_or_list_or_item, list):
        for item in dict_or_list_or_item:
            convert_string_to_objectid(item)

def convert_objectid_to_string(dict_or_list_or_item):
    if isinstance(dict_or_list_or_item, dict):
        for key, value in dict_or_list_or_item.copy().items():
            if isinstance(value, bson.ObjectId):
                dict_or_list_or_item[key] = str(value)
            else:
                convert_objectid_to_string(value)

    elif isinstance(dict_or_list_or_item, list):
        for i, value in enumerate(dict_or_list_or_item.copy()):
            if isinstance(value, bson.ObjectId):
                dict_or_list_or_item[i] = str(value)
            else:
                convert_objectid_to_string(value)


# Class used to fake a cursor
class FakeCursor:

    def __init__(self, target_address, stage_name, indices, 
            filter=None, projection=None, skip=0, limit=0, 
            no_cursor_timeout=False, 
            cursor_type=pymongo.cursor.CursorType.NON_TAILABLE, sort=None, 
            allow_partial_results=False, oplog_replay=False, modifiers=None, 
            batch_size=0, manipulate=True, collation=None, hint=None, 
            max_scan=None, max_time_ms=None, max=None, min=None, 
            return_key=False, show_record_id=False, snapshot=False, 
            comment=None):

        self.target_address = target_address
        self.stage_name = stage_name
        self.indices = indices


        # Optional args
        self._filter = filter
        self._projection = projection
        self._skip = skip
        self._limit = limit
        self._no_cursor_timeout = no_cursor_timeout
        self._cursor_type = cursor_type
        self._sort = sort
        self._allow_partial_results = allow_partial_results
        self._oplog_replay = oplog_replay
        self._modifiers = modifiers
        self._batch_size = batch_size
        self._manipulate = manipulate
        self._collation = collation
        self._hint = hint
        self._max_scan = max_scan
        self._max_time_ms = max_time_ms
        self._max = max
        self._min = min
        self._return_key = return_key
        self._show_record_id = show_record_id
        self._snapshot = snapshot
        self._comment = comment

        self._stored_data = []
        self.array_offset = 0

    # Methods to make the fake cursor an iterable
    def __iter__(self):
        self.iter_counter = 0
        self.array_offset = 0
        self._stored_data = []
        return self

    def __next__(self):
        if self._limit != 0 and self.iter_counter > self._limit:
            raise StopIteration
        else:
            array_index = self.iter_counter - self.array_offset
            if array_index >= len(self._stored_data):
                # Save old cursor values for next calls
                old_skip = self._skip

                # Set the skip and batch_size to return only 1 value
                self._skip = old_skip + self.iter_counter

                # db read
                self.array_offset += len(self._stored_data)
                array_index -= len(self._stored_data)
                self._stored_data = self.load_data()
                if len(self._stored_data) == 0:
                    raise StopIteration
                else:
                    self._skip = old_skip
            self.iter_counter += 1
            return self._stored_data[array_index] 

            

    def __getitem__(self, index):
        if isinstance(index, slice):
            skip = index.start
            end = index.end
            step = index.step
            if step is not None:
                raise IndexError
            elif skip is None:
                self.skip = 0
            elif skip > 0 and (end is None or skip < end):
                self.skip = skip
            else:
                raise IndexError
            if end is None:
                self.limit = 0
            else:
                self._limit = end - skip
            return self

        elif isinstance(index, int):
            if (self._limit != 0 and index >= self._limit) or (not self.is_many and index > 1):
                raise IndexError
            else:
                array_index = self.iter_counter - self.array_offset
                if array_index >= len(self._stored_data) or array_index < 0:
                    # Save old cursor values for next calls
                    old_skip = self._skip

                    # Set the skip 
                    self._skip = old_skip + index

                    # db read
                    result = self.load_data()
                    new_offset = self._skip
                    # restore the cursor value
                    self._skip = old_skip
                    self.has_many = old_has_many
                    if len(result) == 0:
                        raise IndexError
                    else:
                        self._store_data = result
                        self.array_offset = self._skip
                        return result[0]
        else:
            raise pymongo.errors.InvalidOperation

    def batch_size(self, batch_size):
        self._batch_size = batch_size
        return self

    def count(self, with_limit_and_skip=False):
        # db read
        json_entries = self.get_load_data_entries()
        json_entries['with_limit_and_skip'] = with_limit_and_skip
        convert_objectid_to_string(json_entries)
        error = False
        try:
            r = requests.post(self.target_address + count_endpoint, json=json_entries, timeout=600)
        except (socket.timeout) as e:
            error = True
        #Check if sucessful
        if not r.ok or error:
            error = True
        if error:
            assert(not error)
        else:
            data_json = r.json()
            return data_json['count']

    def distinct(self, key):
        # db read
        json_entries = self.get_load_data_entries()
        json_entries['distinct_key'] = key
        convert_objectid_to_string(json_entries)
        error = False
        try:
            r = requests.post(self.target_address + distinct_endpoint, json=json_entries, timeout=600)
        except (socket.timeout) as e:
            error = True
        #Check if sucessful
        if not r.ok or error:
            error = True
        if error:
            assert(not error)
        else:
            data_json = r.json()
            return data_json['distinct']


    def limit(self, limit):
        self._limit = limit
        return self

    def sort(self, key_or_list, direction=None):
        if isinstance(key_or_list, list):
            self._sort = key_or_list
        else:
            self._sort = [(key_or_list, direction)]
        return self

    def get_load_data_entries(self):
        json_entries = dict()
        json_entries['stage_name'] = self.stage_name
        json_entries['indices'] = self.indices
        
        # Optional args
        json_entries['filter'] = self._filter
        json_entries['projection'] = self._projection
        json_entries['skip'] = self._skip
        json_entries['limit'] = self._limit
        json_entries['no_cursor_timeout'] = self._no_cursor_timeout
        json_entries['cursor_type'] = self._cursor_type
        json_entries['sort'] = self._sort
        json_entries['allow_partial_results'] = self._allow_partial_results
        json_entries['oplog_replay'] = self._oplog_replay
        json_entries['modifiers'] = self._modifiers
        json_entries['batch_size'] = self._batch_size
        json_entries['manipulate'] = self._manipulate
        json_entries['collation'] = self._collation
        json_entries['hint'] = self._hint
        json_entries['max_scan'] = self._max_scan
        json_entries['max_time_ms'] = self._max_time_ms
        json_entries['max'] = self._max
        json_entries['min'] = self._min
        json_entries['return_key'] = self._return_key
        json_entries['show_record_id'] = self._show_record_id
        json_entries['snapshot'] = self._snapshot
        json_entries['comment'] = self._comment

        return json_entries

    def load_data(self):
        json_entries = self.get_load_data_entries()
        convert_objectid_to_string(json_entries)
        error = False
        try:
            r = requests.post(self.target_address + find_endpoint, json=json_entries, timeout=600)
        except (socket.timeout) as e:
            error = True
        #Check if sucessful
        if not r.ok or error:
            error = True
        if error:
            assert(not error)
        else:
            data_json = r.json()
            convert_string_to_objectid(data_json)
            return data_json['data']



# Classes used to fake results from insert, update, and delete

class FakeInsertOneResult:

    def __init__(self, target_address, stage_name, indices, data_dict,
            bypass_document_validation):

        # Setup the json
        json_entries = dict()
        json_entries['stage_name'] = stage_name
        json_entries['indices'] = indices
        json_entries['data'] = data_dict
        json_entries['is_many'] = False
        json_entries['bypass_document_validation'] = bypass_document_validation
        # Make the call to db insert one
        convert_objectid_to_string(json_entries)
        error = False
        try:
            r = requests.post(target_address + insert_endpoint, json=json_entries, timeout=600)
        except (socket.timeout) as e:
            error = True
        #Check if sucessful
        if not r.ok or error:
            error = True
        if error:
            assert(not error)
        else:
            data_json = r.json()
            # Fill in with the results of the db call
            self.acknowledged = data_json['acknowledged']
            self.inserted_id = bson.ObjectId(data_json['inserted_id'])

class FakeInsertManyResult:

    def __init__(self, target_address, stage_name, indices, data_dict, ordered,
            bypass_document_validation):

        # Setup the json
        json_entries = dict()
        json_entries['stage_name'] = stage_name
        json_entries['indices'] = indices
        json_entries['data'] = data_dict
        json_entries['is_many'] = True
        json_entries['ordered'] = ordered
        json_entries['bypass_document_validation'] = bypass_document_validation
        # Make the call to db insert one
        convert_objectid_to_string(json_entries)
        error = False
        try:
            r = requests.post(target_address + insert_endpoint, json=json_entries, timeout=600)
        except (socket.timeout) as e:
            error = True
        #Check if sucessful
        if not r.ok or error:
            error = True
        if error:
            assert(not error)
        else:
            data_json = r.json()
            # Fill in with the results of the db call
            self.acknowledged = data_json['acknowledged']
            self.inserted_ids = [bson.ObjectId(_id) for _id in data_json['inserted_ids']]


class FakeUpdateResult:

    def __init__(self, target_address, stage_name, indices, query_dict, 
            data_dict, is_many, is_update, upsert, bypass_document_validation, 
            collation):

        # Setup the json
        json_entries = dict()
        json_entries['stage_name'] = stage_name
        json_entries['indices'] = indices
        json_entries['query'] = query_dict
        json_entries['data'] = data_dict
        json_entries['is_many'] = is_many
        json_entries['upsert'] = upsert
        json_entries['bypass_document_validation'] = bypass_document_validation
        json_entries['collation'] = collation
        # Make the call to db insert one
        convert_objectid_to_string(json_entries)
        error = False
        try:
            if is_update:
                r = requests.post(target_address + update_endpoint, json=json_entries, timeout=600)
            else:
                r = requests.post(target_address + replace_one_endpoint, json=json_entries, timeout=600)

        except (socket.timeout) as e:
            error = True
        #Check if sucessful
        if not r.ok or error:
            error = True
        if error:
            assert(not error)
        else:
            data_json = r.json()
            convert_string_to_objectid(data_json)
            # Fill in with the results of the db call
            self.acknowledged = data_json['acknowledged']
            self.matched_count = data_json['matched_count']
            self.modified_count = data_json['modified_count']
            self.raw_result = data_json['raw_result']
            upserted_id = data_json['upserted_id']
            if upserted_id is not None:
                upserted_id = bson.ObjectId(upserted_id)
            self.upserted_id = upserted_id

class FakeDeleteResult:

    def __init__(self, target_address, stage_name, indices, query_dict, is_many, collation):

        # Setup the json
        json_entries = dict()
        json_entries['stage_name'] = stage_name
        json_entries['indices'] = indices
        json_entries['query'] = query_dict
        json_entries['is_many'] = is_many
        json_entries['collation'] = collation
        # Make the call to db insert one
        convert_objectid_to_string(json_entries)
        error = False
        try:
            r = requests.post(target_address + delete_endpoint, json=json_entries, timeout=600)
        except (socket.timeout) as e:
            error = True
        #Check if sucessful
        if not r.ok or error:
            error = True
        if error:
            assert(not error)
        else:
            data_json = r.json()
            # Fill in with the results of the db call
            convert_string_to_objectid(data_json)
            self.acknowledged = data_json['acknowledged']
            self.deleted_count = data_json['deleted_count']
            self.raw_result = data_json['raw_result']

# Classes used to replace the db() calls
class AbstractCollection:
    def __init__(self, target_address, stage_name, indices):
        self.target_address = target_address
        self.stage_name = stage_name
        self.indices = indices

    def insert(self, doc_or_docs, manipulate=True, check_keys=True,
            continue_on_error=False, **kwargs):
        json_entries = dict()
        json_entries['stage_name'] = self.stage_name
        json_entries['indices'] = self.indices

        json_entries['doc_or_docs'] = doc_or_docs
        json_entries['manipulate'] = manipulate
        json_entries['check_keys'] = check_keys
        json_entries['continue_on_error'] = continue_on_error
        optional_args = ['w', 'wtimeout', 'j', 'fsync']
        for arg in optional_args:
            if arg in kwargs:
                json_entries[arg] = kwargs[arg]

        convert_objectid_to_string(json_entries)
        error = False
        try:
            r = requests.post(self.target_address + insert_deprecated_endpoint, json=json_entries, timeout=600)
        except (socket.timeout) as e:
            error = True
        #Check if sucessful
        if not r.ok or error:
            error = True
        if error:
            assert(not error)
        else:
            data_json = r.json()
            result = data_json['resp']
            if isinstance(result, list):
                if result[0] is not None:
                    result = [bson.ObjectId(_id) for _id in result]
            else:
                result = bson.ObjectId(result)
            return data_json['resp']



    def insert_many(self, data_dict_list, ordered=True, 
            bypass_document_validation=False):
        return FakeInsertManyResult(self.target_address, self.stage_name,
                self.indices, data_dict_list, ordered,
                bypass_document_validation)

    def insert_one(self, data_dict, bypass_document_validation=False):
        return FakeInsertOneResult(self.target_address, self.stage_name,
                self.indices, data_dict, bypass_document_validation)

    def update(self, spec, document, upsert=False, manipulate=False,
            multi=False, check_keys=True, **kwargs):
        json_entries = dict()
        json_entries['stage_name'] = self.stage_name
        json_entries['indices'] = self.indices

        json_entries['spec'] = spec
        json_entries['document'] = document
        json_entries['upsert'] = upsert
        json_entries['manipulate'] = manipulate
        json_entries['check_keys'] = check_keys
        optional_args = ['multi', 'w', 'wtimeout', 'j', 'fsync']
        for arg in optional_args:
            if arg in kwargs:
                json_entries[arg] = kwargs[arg]

        convert_objectid_to_string(json_entries)
        error = False
        try:
            r = requests.post(self.target_address + update_deprecated_endpoint, json=json_entries, timeout=600)
        except (socket.timeout) as e:
            error = True
        #Check if sucessful
        if not r.ok or error:
            error = True
        if error:
            assert(not error)
        else:
            data_json = r.json()
            convert_string_to_objectid(data_json)
            return data_json['resp']

    def update_many(self, query_dict, data_dict, upsert=False, 
            array_filters=None, bypass_document_validation=False, 
            collation=None):
        return FakeUpdateResult(self.target_address, self.stage_name,
                self.indices, query_dict, data_dict, True, True, upsert=upsert,
                bypass_document_validation=bypass_document_validation,
                collation=collation)
    
    def update_one(self, query_dict, data_dict, upsert=False,
            bypass_document_validation=False, collation=None):
        return FakeUpdateResult(self.target_address, self.stage_name,
                self.indices, query_dict, data_dict, False, True, upsert=upsert,
                bypass_document_validation=bypass_document_validation,
                collation=collation)

    def replace_one(self, query_dict, data_dict, upsert=False,
            bypass_document_validation=False, collation=None):
        return FakeUpdateResult(self.target_address, self.stage_name,
                self.indices, query_dict, data_dict, False, False, upsert=upsert,
                bypass_document_validation=bypass_document_validation,
                collation=collation)

    def delete_many(self, query_dict, collation=None, session=None):
        return FakeDeleteResult(self.target_address, self.stage_name,
                self.indices, query_dict, True, collation)

    def delete_one(self, query_dict, collation=None):
        return FakeDeleteResult(self.target_address, self.stage_name,
                self.indices, query_dict, False, collation)

    def find(self, filter=None, *args, **kwargs):
        return FakeCursor(self.target_address, self.stage_name,
                self.indices, filter, *args, **kwargs)

    def find_one(self, filter=None, projection=None, 
            skip=0, limit=0, no_cursor_timeout=False, 
            cursor_type=pymongo.cursor.CursorType.NON_TAILABLE, sort=None, 
            allow_partial_results=False, oplog_replay=False, modifiers=None, 
            batch_size=0, manipulate=True, collation=None, hint=None, 
            max_scan=None, max_time_ms=None, max=None, min=None, 
            return_key=False, show_record_id=False, snapshot=False, 
            comment=None):

        json_entries = dict()
        json_entries['stage_name'] = self.stage_name
        json_entries['indices'] = self.indices
        
        # Optional args
        json_entries['filter'] = filter
        json_entries['projection'] = projection
        json_entries['skip'] = skip
        json_entries['limit'] = limit
        json_entries['no_cursor_timeout'] = no_cursor_timeout
        json_entries['cursor_type'] = cursor_type
        json_entries['sort'] = sort
        json_entries['allow_partial_results'] = allow_partial_results
        json_entries['oplog_replay'] = oplog_replay
        json_entries['modifiers'] = modifiers
        json_entries['batch_size'] = batch_size
        json_entries['manipulate'] = manipulate
        json_entries['collation'] = collation
        json_entries['hint'] = hint
        json_entries['max_scan'] = max_scan
        json_entries['max_time_ms'] = max_time_ms
        json_entries['max'] = max
        json_entries['min'] = min
        json_entries['return_key'] = return_key
        json_entries['show_record_id'] = show_record_id
        json_entries['snapshot'] = snapshot
        json_entries['comment'] = comment

        convert_objectid_to_string(json_entries)
        error = False
        try:
            r = requests.post(self.target_address + find_one_endpoint, json=json_entries, timeout=600)
        except (socket.timeout) as e:
            error = True
        #Check if sucessful
        if not r.ok or error:
            error = True
        if error:
            assert(not error)
        else:
            data_json = r.json()
            convert_string_to_objectid(data_json)
            return data_json['data']

class AnalysisTimeseriesCollection(AbstractCollection):

    def __init__(self, target_address):
        indices_dict = dict()
        indices_dict["data.start_ts"] = [[pymongo.DESCENDING], True]
        indices_dict["data.end_ts"] = [[pymongo.DESCENDING], True]
        indices_dict["data.start_loc"] = [[pymongo.GEOSPHERE], True]
        indices_dict["data.end_loc"] = [[pymongo.GEOSPHERE], True]
        self.append_local_dt_indices(indices_dict, "data.start_local_dt")
        self.append_local_dt_indices(indices_dict, "data.end_local_dt")

        # places and stops
        indices_dict["data.enter_ts"] = [[pymongo.DESCENDING], True]
        indices_dict["data.exit_ts"] = [[pymongo.DESCENDING], True]
        self.append_local_dt_indices(indices_dict, "data.enter_local_dt")
        self.append_local_dt_indices(indices_dict, "data.exit_local_dt")

        indices_dict["data.location"] = [[pymongo.GEOSPHERE], True]
        indices_dict["data.duration"] = [[pymongo.DESCENDING], True]
        indices_dict["data.mode"] = [[pymongo.HASHED], True]
        indices_dict["data.section"] = [[pymongo.HASHED], True]

        # recreated location
        indices_dict["data.ts"] = [[pymongo.DESCENDING], True]
        indices_dict["data.loc"] = [[pymongo.GEOSPHERE], True]
        self.append_local_dt_indices(indices_dict, "data.local_dt") # recreated location

        super().__init__(target_address, "Stage_analysis_timeseries", indices_dict)

    def append_local_dt_indices(self, indices_dict, index_prefix):
        indices_dict["{}.year".format(index_prefix)] = [[pymongo.DESCENDING], True]
        indices_dict["{}.month".format(index_prefix)] = [[pymongo.DESCENDING], True]
        indices_dict["{}.day".format(index_prefix)] = [[pymongo.DESCENDING], True]
        indices_dict["{}.hour".format(index_prefix)] = [[pymongo.DESCENDING], True]
        indices_dict["{}.minute".format(index_prefix)] = [[pymongo.DESCENDING], True]
        indices_dict["{}.second".format(index_prefix)] = [[pymongo.DESCENDING], True]
        indices_dict["{}.weekday".format(index_prefix)] = [[pymongo.DESCENDING], True]

class TimeseriesCollection(AbstractCollection):

    def __init__(self, target_address):
        indices_dict = dict()
        indices_dict["metadata.key"] =[[pymongo.HASHED], False]
        indices_dict['metadata.write_ts'] = [[pymongo.DESCENDING], False]
        indices_dict['data.ts'] = [[pymongo.DESCENDING], True]
        indices_dict['data.loc'] = [[pymongo.GEOSPHERE], True]
        super().__init__(target_address, "Stage_timeseries", indices_dict)

class UsercacheCollection(AbstractCollection):

    def __init__(self, target_address):
        indices_dict = dict()
        index1 = ["metadata.write_ts",
                "metadata.key"]
        index_one = "metadata.type"
        for elem in index1:
            index_one += "\n" + elem
        indices_dict[index_one] =[[pymongo.ASCENDING, pymongo.ASCENDING, pymongo.ASCENDING], False]
        indices_dict['metadata.write_ts'] = [[pymongo.DESCENDING], False]
        indices_dict['data.ts'] = [[pymongo.DESCENDING], True]
        super().__init__(target_address, "Stage_usercache", indices_dict)

class CalendarCollection(AbstractCollection):

    def __init__(self, target_address):
        indices_dict = dict()
        index1 = ["data.attendees", "data.start_time", "data.end_time", "data.ts", "data.geo"]
        index_one = "metadata.type"
        for elem in index1:
            index_one += "\n" + elem
        indices_dict[index_one] =[[pymongo.ASCENDING, pymongo.ASCENDING, 
            pymongo.ASCENDING, pymongo.ASCENDING, pymongo.ASCENDING, 
            pymongo.GEOSPHERE], False]
        super().__init__(target_address, "Stage_calendar", indices_dict)


### End of classes

def request_service(username, service_name):
    controller_addr = controller_ip + ":" + str(controller_port)
    json_values = dict()
    json_values['user'] = username
    json_values['service'] = service_name
    error = False
    try:
        r = requests.post (controller_addr + service_endpoint, json=json_values)
    except (socket.timeout) as e:
        error = True
    #Check if sucessful
    if not r.ok or error:
        error = True
    if error:
        assert(not error)
    else:
        data_json = r.json()
        return data_json['address']

def deduct_budget(pm_address, privacy_cost):
    json_entries = dict()
    json_entries['privacy_cost'] = privacy_cost
    error = False
    try:
        r = requests.post(pm_address + privacy_budget_endpoint, json=json_entries, timeout=600)
    except (socket.timeout) as e:
        error = True
    #Check if sucessful
    if not r.ok or error:
        error = True
    if error:
        assert(not error)
    else:
        data_json = r.json()
        print("New budget: {}".format(data_json['budget']))
        return data_json['success']
