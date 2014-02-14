from types import NoneType
import fuzzer.sqliteengine as SQLEngine
import random
import datetime

class Fuzzer(object):
    """
    Fuzzer is used to either generate fuzzed values, or to read fuzzed values
    and catch up or tail an already running fuzzer.
    """
    def __init__(self, database="fuzzerdb.db", cache_tablenames=True,
                 table_name=datetime.datetime.today().strftime(
                                                     "attempts%m%d%y")):

        self.sql_engine = SQLEngine.SQLiteEngine(database,
                          tables_to_cache=cache_tablenames)
        self.table_name = table_name
    def initialize(self):
        """
        Initialize the database, if there is not already one.
        """
        try:
            self.sql_engine.create_database(
                           self.table_name,
                           ("attempt_id", "INTEGER PRIMARY KEY"),
                           ("attempted", "TEXT"),
                           ("prohibited", "TEXT"),
                           ("successful", "BOOL"),
                           ("created_at", "TEXT"),
                           ("updated_at", "TEXT")
                           )
        except SQLEngine.TableAlreadyExists:
            pass
        return True
    def commit_to_database(self):
        """
        Trigger SQL engine to commit all values awaiting insertion.
        """
        self.sql_engine.commit_pool()
    def _increment(self, values, index, maximum=255, reset=True,
                  _called_from_func=False):
        """
        Handles incrementation for fuzzer.
        """
        if index >= 0:
            if (values[index]+1) >= maximum:
                if _called_from_func and index == 0:
                    raise MaximumIncrementReached(
                          "Incrementation limit reached")
                if reset:
                    values[index] = 0
                try:
                    self._increment(values, index - 1,
                                   maximum=maximum, reset=reset,
                                   _called_from_func=True
                                   )
                except MaximumIncrementReached:
                    return
            else:
                values[index] = values[index] + 1
                return

    def fuzz(self, random_generation=False, prohibit=None,
                   length=5, output_format="{fuzzed_string}",
                   character_evaluator=chr, maximum=255):
        """
        Generates all possibilities with a given length. If random is passed,
        it will generate random values with a given length in a range between
        0 and `maximum`. The character_evaluator will be used to convert the
        number into its character form.
        """
        if maximum > 255 and character_evaluator == chr:
            raise TooHighForChr("`maximum` is too large for chr,\
                                 must be between 0 and 255.")
        if prohibit != None:
            if not isinstance(prohibit, list):
                raise TypeError("`prohibit` must be a list.")
            else:
                for value in prohibit:
                    if not isinstance(value, str):
                        raise TypeError("Values in prohibit must be a string.")
                    else:
                        if len(value) > 1:
                            raise ValueError("Values in prohibit must only be\
                                              one character long.")
        if not isinstance(output_format, str):
            raise TypeError("output_format should be a string.")
        if not isinstance(random_generation, bool):
            raise TypeError("random_generation should be a bool.")

        if (not random_generation) and (prohibit == None):
            done = False
            temp_list = [0]*length
            while not done:
                attempt = output_format.format(fuzzed_string="".join(
                list(character_evaluator(character) for character in temp_list))
                )
                yield Result(self, attempt, prohibited=prohibit)
                try:
                    self._increment(temp_list, length - 1, maximum=maximum)
                except MaximumIncrementReached:
                    done = True
        if (not random_generation) and (prohibit != None):
            done = False
            pass_attempt = False
            temp_list = [0]*length
            while not done:
                attempt = output_format.format(fuzzed_string="".join(
                list(character_evaluator(character) for character in temp_list))
                )
                for character in attempt:
                    if character in prohibit:
                        pass_attempt = True
                if pass_attempt:
                    pass_attempt = False
                    try:
                        self._increment(temp_list, 0, maximum=maximum)
                    except MaximumIncrementReached:
                        done = True
                    continue
                else:
                    yield Result(self, attempt, prohibited=prohibit)
                    try:
                        self._increment(temp_list, 0, maximum=maximum)
                    except MaximumIncrementReached:
                        done = True
        if (random_generation) and (prohibit == None):
            while True:
                attempt = output_format.format(fuzzed_string="".join(
                list(character_evaluator(random.randrange(0, maximum))
                     for index in range(length))
                ))
                yield Result(self, attempt, prohibited=prohibit)
        if (random_generation) and (prohibit != None):
            while True:
                temp_list = [0]*length
                for index in range(length):
                    done = False
                    while not done:
                        char_value_attempt = random.randrange(0, maximum)
                        if character_evaluator(char_value_attempt) in prohibit:
                            continue
                        else:
                            temp_list[index] = char_value_attempt
                            done = True
                attempt = "".join(
                list(character_evaluator(value) for value in temp_list
                ))
                yield Result(self, attempt, prohibited=prohibit)
    def tail(self, table_name, select_conditions={},
             order_by="created_at ASC"):

        if not isinstance(select_conditions, dict):
            raise TypeError("select_conditions must be a dict.")
        query = "SELECT * FROM {table_name} WHERE".format(
                    table_name=table_name
                )
        first_iteration = True
        for keyword, condition in select_conditions.iteritems():
            if not isinstance(condition, NoneType)\
               and not isinstance(keyword, NoneType)\
               and not keyword == "":
                if first_iteration:
                    query += " {keyword} = {condition}".format(
                            keyword=keyword,
                            condition=repr(condition)\
                                      if isinstance(condition, str)\
                                      else condition
                        )
                    first_iteration = False
                else:
                    query += " AND {keyword} = {condition}".format(
                            keyword=keyword,
                            condition=repr(condition)\
                                      if isinstance(condition, str)\
                                      else condition
                        )
        if not isinstance(order_by, str):
            raise TypeError("order_by must be a string.")

        order_set = False
        if order_by == "":
            #end of query
            query += ";"
        else:
            #ordering of query
            order_set = True
            query_without_order = query
            query += " ORDER BY {order_by};".format(
                    order_by=order_by
                )

        first_result = None
        last_result = None
        tail_from_created = False
        while True:
            #after all values have been iterated currently in database,
            #this waits and watches the DB for any new rows added.
            if tail_from_created:
                if order_set:
                    #override the order, pull by when it was created to
                    #grab latest generation
                    query = query_without_order + " ORDER BY created_at DESC LIMIT 1;"
                else:
                    #add our order to the query, there isnt one already
                    query = query.rstrip(";") + " ORDER BY created_at DESC LIMIT 1;"
                while True:
                    #convert out of a generator and pull the result. Limited to 1
                    result = list(self.sql_engine.read_query(query))[0]
                    if isinstance(last_result, NoneType):
                        last_result = result
                    else:
                        if last_result == result:
                            pass
                        else:
                            last_result = result
                            yield Result(self, result[1], prohibited=result[2])
            else:
                for index, result in enumerate(self.sql_engine.read_query(query)):
                    if index == 0:
                        if isinstance(first_result, NoneType):
                            first_result = result
                        else:
                            if result == first_result:
                                tail_from_created = True
                                last_result = result
                                break
                    yield Result(self, result[1], prohibited=result[2])



class Result(object):
    """
    Used to determine success or failure of an attempt, then submit value into
    engine insertion queue.
    """
    def __init__(self, fuzzer_instance, attempt, prohibited=None):
        self.engine_instance = fuzzer_instance.sql_engine
        self.table_name = fuzzer_instance.table_name
        self.value = attempt
        self.prohibited = prohibited
    def success(self):
        """
        Register with the SQL engine that the result should be entered as a
        success.
        """
        self.engine_instance.append_to_pool(self._generate_item(True),
                                            self.table_name)
    def fail(self):
        """
        Register with the SQL engine that the result should be entered as a
        failure.
        """
        self.engine_instance.append_to_pool(self._generate_item(False),
                                            self.table_name)
    def _generate_item(self, success_value):
        """
        Create the item to submit to the SQL engine.
        """
        return {"created_at": datetime.datetime.now().strftime("%c"),
                "updated_at": datetime.datetime.now().strftime("%c"),
                "prohibited": "" if isinstance(self.prohibited, NoneType) \
                                 else self.prohibited,
                "attempted" : self.value,
                "successful": success_value}

class GeneralException(Exception):
    """
    Baseclass for all exceptions raised by Fuzzer.
    """
    def __init__(self, message):
        self.message = message
    def __str__(self):
        return str(self.message)
    def __repr__(self):
        return repr(self.message)

class TooHighForChr(GeneralException):
    """
    Raised to handle a value being too large for `chr`.
    """
    pass
class MaximumIncrementReached(GeneralException):
    """
    Raised to alert that all elements of the list have reached their maximum.
    """
    pass
