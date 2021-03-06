# -*- coding: utf-8 -*-
"""
 db.py

 Copyright (C) 2017-2031  YuHuan Chow <chowyuhuan@gmail.com>

"""

import MySQLdb
import MySQLdb.cursors
from DBUtils import PersistentDB

from log import LogManager
from thread import ThreadPool, WorkRequest, NoResultsPending
from timer import Timer
from settings import DATABASES

class DataBaseService(object):

    """Provide database service. """

    services = dict()

    def __init__(self):
        super(DataBaseService, self).__init__()

    @staticmethod
    def get_service(db_name):
        if db_name in DataBaseService.services:
            return DataBaseService.services[db_name]
        else:
            service = DatabaseProxy(DATABASES[db_name]['ENGINE'],
                                    DATABASES[db_name]['CONFIG'])
            DataBaseService.services[db_name] = service
            return service


OP_CREATE_TABLE = 1
OP_DROP_TABLE = 2
OP_INSERT = 3
OP_DELETE = 4
OP_UPDATE = 5
OP_FIND = 6
OP_COUNT = 7

class DatabaseProxy(object):

    def __init__(self, engine, db_config):
        super(DatabaseProxy, self).__init__()
        self.logger = LogManager.get_logger("db." + self.__class__.__name__)
        self.engine = engine
        if self.engine == 'mysql':
            self.db_client = MysqlDatabase(db_config)
            self.db_client.connect()
            self.logger.info('init: %s', 'Database engine MySQLdb.')
        else:
            self.logger.error('init: err=%s', 'Database engine not find.')
            raise "Database engine not find."
        self.connected = self.db_client.connected
        self.data_types = self.db_client.data_types
        self.operators = self.db_client.operators
        self.format_string = self.db_client.format_string
        self.thread_num = 10
        self.request_pool = ThreadPool(self.thread_num)
        self.request_time = 0.01
        self.timer = Timer.add_repeat_timer(self.request_time, self.request_result)

    def __exit__(self):
        self.request_pool.dismissWorkers(self.thread_num)
        self.db_client = None
        self.timer.cancel()

    def request_result(self):
        try:
            self.request_pool.poll()
        except NoResultsPending:
            pass

    def execute_callback(self, request, result, callback):
        self.logger.info('execute_callback: %s', str(result))
        if result:
            try:
                callback(result[0], result[1])
            except:
                self.logger.warn('execute_callback: %s', 'Send callback error.')
                self.logger.log_last_except()

    def execute(self, op, params, fetchone=False, callback=None):
        if self.db_client.connected:
            request = WorkRequest(
                self.db_client.execute,
                (op, params, fetchone),
                callback=lambda requset, result: self.execute_callback(
                    request,
                    result,
                    callback))
            self.request_pool.putRequest(request)
            return True
        else:
            return False

    def create_table(self, table, columns, callback):
        params = {
            "table": table,
            "definition": ", ".join(columns)
        }
        return self.execute(OP_CREATE_TABLE, params, callback=callback)

    def drop_table(self, table, callback):
        params = {
            "table": table
        }
        return self.execute(OP_DROP_TABLE, params, callback=callback)

    def insert(self, table, values, callback):
        self.db_client.format_strings(values)
        params = {
            "table": table,
            "values": ", ".join(values)
        }
        return self.execute(OP_INSERT, params, callback=callback)

    def delete(self, table, condition, callback):
        params = {
            "table": table,
            "condition": condition and " ".join(condition) or condition,
        }
        return self.execute(OP_DELETE, params, callback=callback)

    def update(self, table, expressions, condition, callback):
        params = {
            "table": table,
            "expressions": " ".join(expressions),
            "condition": condition and " ".join(condition) or condition,
        }
        return self.execute(OP_UPDATE, params, callback=callback)

    def find(self, table, columns, condition, callback):
        params = {
            "columns": ", ".join(columns),
            "table": table,
            "condition": condition and " ".join(condition) or condition,
        }
        return self.execute(OP_FIND, params, callback=callback)

    def findone(self, table, columns, condition, callback):
        params = {
            "columns": ", ".join(columns),
            "table": table,
            "condition": condition and " ".join(condition) or condition,
        }
        return self.execute(OP_FIND, params, fetchone=True, callback=callback)

    def count(self, table, column, callback):
        params = {
            "column": " ".join(column),
            "table": table,
        }
        return self.execute(OP_COUNT, params, callback=callback)


class MysqlDatabase(object):
    data_types = {
        'AutoField': 'integer AUTO_INCREMENT',
        'BigAutoField': 'bigint AUTO_INCREMENT',
        'BinaryField': 'longblob',
        'BooleanField': 'bool',
        'CharField': 'varchar(%(max_length)s)',
        'CommaSeparatedIntegerField': 'varchar(%(max_length)s)',
        'DateField': 'date',
        'DateTimeField': 'datetime',
        'DecimalField': 'numeric(%(max_digits)s, %(decimal_places)s)',
        'DurationField': 'bigint',
        'FileField': 'varchar(%(max_length)s)',
        'FilePathField': 'varchar(%(max_length)s)',
        'FloatField': 'double precision',
        'IntegerField': 'integer',
        'BigIntegerField': 'bigint',
        'IPAddressField': 'char(15)',
        'GenericIPAddressField': 'char(39)',
        'NullBooleanField': 'bool',
        'OneToOneField': 'integer',
        'PositiveIntegerField': 'integer UNSIGNED',
        'PositiveSmallIntegerField': 'smallint UNSIGNED',
        'SlugField': 'varchar(%(max_length)s)',
        'SmallIntegerField': 'smallint',
        'TextField': 'longtext',
        'TimeField': 'time',
        'UUIDField': 'char(32)',
    }

    operators = {
        'exact': '= %s',
        'iexact': 'LIKE %s',
        'contains': 'LIKE BINARY %s',
        'icontains': 'LIKE %s',
        'regex': 'REGEXP BINARY %s',
        'iregex': 'REGEXP %s',
        'gt': '> %s',
        'gte': '>= %s',
        'lt': '< %s',
        'lte': '<= %s',
        'startswith': 'LIKE BINARY %s',
        'endswith': 'LIKE BINARY %s',
        'istartswith': 'LIKE %s',
        'iendswith': 'LIKE %s',
    }

    def __init__(self, db_config):
        super(MysqlDatabase, self).__init__()
        self.logger = LogManager.get_logger("db." + self.__class__.__name__)
        self.db_config = db_config
        self.host = self.db_config["HOST"]
        self.port = self.db_config["PORT"]
        self.user = self.db_config["USER"]
        self.passwd = self.db_config["PASSWORD"]
        self.db = self.db_config["NAME"]
        self.connected = False
        self.pool = None

    def connect(self):
        try:
            self.pool = PersistentDB.PersistentDB(creator=MySQLdb, maxusage=1000,
                                                  host=self.host,
                                                  port=self.port,
                                                  user=self.user,
                                                  passwd=self.passwd,
                                                  db=self.db,
                                                  charset='utf8',
                                                  use_unicode=True,
                                                  cursorclass=MySQLdb.cursors.DictCursor)
            self.connected = True
        except (MySQLdb.Error, PersistentDB.PersistentDBError):
            self.logger.error('connect: err=%s', 'Connect db failed.')
            self.logger.log_last_except()

    def execute(self, op, params, fetchone=False, args=None):
        """This function will be run by Multi-thread."""

        sql = None
        if op == OP_CREATE_TABLE:
            sql = MysqlSchema.sql_create_table % params

        elif op == OP_DROP_TABLE:
            sql = MysqlSchema.sql_delete_table % params

        elif op == OP_INSERT:
            sql = MysqlSchema.sql_insert % params

        elif op == OP_DELETE:
            if params['condition']:
                sql = MysqlSchema.sql_delete_where % params
            else:
                sql = MysqlSchema.sql_delete % params

        elif op == OP_UPDATE:
            if params['condition']:
                sql = MysqlSchema.sql_update_where% params
            else:
                sql = MysqlSchema.sql_update % params

        elif op == OP_FIND:
            if params['condition']:
                sql = MysqlSchema.sql_select_where% params
            else:
                sql = MysqlSchema.sql_select % params

        elif op == OP_COUNT:
            sql = MysqlSchema.sql_count % params

        else:
            self.logger.error('execute: %s err=%s', sql, 'Unknown database operation.')
            return False, None

        self.logger.info('execute: %s', sql)
        try:
            # import threading
            # print threading.current_thread().getName()
            connection = self.pool.connection()
            cursor = connection.cursor()
            # args is None means no string interpolation
            cursor.execute(sql, args)
            # MySQLdb autocommit is false by default, so commit here.
            connection.commit()
            if fetchone:
                return True, cursor.fetchone()
            else:
                return True, cursor.fetchall()
        except (MySQLdb.OperationalError, MySQLdb.ProgrammingError,
                PersistentDB.PersistentDBError):
            # Map some error codes to IntegrityError, since they seem to be
            self.logger.log_last_except()
            return False, None
        finally:
            cursor.close()
            connection.close()

    @classmethod
    def format_strings(cls, values):
        for i in range(0, len(values)):
            value = values[i]
            values[i] = type(value) == str and "'%s'" % value or str(value)

    @classmethod
    def format_string(cls, value):
        return type(value) == str and "'%s'" % value or str(value)


class BaseSchema(object):
    sql_create_table = "CREATE TABLE %(table)s (%(definition)s)"
    sql_rename_table = "ALTER TABLE %(old_table)s RENAME TO %(new_table)s"
    sql_retablespace_table = "ALTER TABLE %(table)s SET TABLESPACE %(new_tablespace)s"
    sql_delete_table = "DROP TABLE %(table)s CASCADE"

    sql_create_column = "ALTER TABLE %(table)s ADD COLUMN %(column)s %(definition)s"
    sql_alter_column = "ALTER TABLE %(table)s %(changes)s"
    sql_alter_column_type = "ALTER COLUMN %(column)s TYPE %(type)s"
    sql_alter_column_null = "ALTER COLUMN %(column)s DROP NOT NULL"
    sql_alter_column_not_null = "ALTER COLUMN %(column)s SET NOT NULL"
    sql_alter_column_default = "ALTER COLUMN %(column)s SET DEFAULT %(default)s"
    sql_alter_column_no_default = "ALTER COLUMN %(column)s DROP DEFAULT"
    sql_delete_column = "ALTER TABLE %(table)s DROP COLUMN %(column)s CASCADE"
    sql_rename_column = "ALTER TABLE %(table)s RENAME COLUMN %(old_column)s TO %(new_column)s"
    sql_update_with_default = "UPDATE %(table)s SET %(column)s = %(default)s WHERE %(column)s IS NULL"

    sql_create_check = "ALTER TABLE %(table)s ADD CONSTRAINT %(name)s CHECK (%(check)s)"
    sql_delete_check = "ALTER TABLE %(table)s DROP CONSTRAINT %(name)s"

    sql_create_unique = "ALTER TABLE %(table)s ADD CONSTRAINT %(name)s UNIQUE (%(columns)s)"
    sql_delete_unique = "ALTER TABLE %(table)s DROP CONSTRAINT %(name)s"

    sql_create_fk = (
        "ALTER TABLE %(table)s ADD CONSTRAINT %(name)s FOREIGN KEY (%(column)s) "
        "REFERENCES %(to_table)s (%(to_column)s) DEFERRABLE INITIALLY DEFERRED"
    )
    sql_create_inline_fk = None
    sql_delete_fk = "ALTER TABLE %(table)s DROP CONSTRAINT %(name)s"

    sql_create_index = "CREATE INDEX %(name)s ON %(table)s (%(columns)s)%(extra)s"
    sql_delete_index = "DROP INDEX %(name)s"

    sql_create_pk = "ALTER TABLE %(table)s ADD CONSTRAINT %(name)s PRIMARY KEY (%(columns)s)"
    sql_delete_pk = "ALTER TABLE %(table)s DROP CONSTRAINT %(name)s"

    sql_insert = "INSERT INTO %(table)s VALUE (%(values)s)"
    sql_delete = "DELETE FROM %(table)s"
    sql_delete_where = "DELETE FROM %(table)s WHERE %(condition)s"
    sql_delete_where_select = "DELETE FROM %(table)s WHERE %(columns) IN %(select)s"
    sql_update = "UPDATE %(table)s SET %(expressions)s"
    sql_update_where = "UPDATE %(table)s SET %(expressions)s WHERE %(condition)s"
    sql_update_where_select = "UPDATE %(table)s SET %(expressions)s WHERE %(columns) IN %(select)s"
    sql_select = "SELECT %(columns)s FROM %(table)s"
    sql_select_where = "SELECT %(columns)s FROM %(table)s WHERE %(condition)s"
    sql_count = "SELECT COUNT(%(column)s) FROM %(table)s"


class MysqlSchema(BaseSchema):
    sql_rename_table = "RENAME TABLE %(old_table)s TO %(new_table)s"

    sql_alter_column_null = "MODIFY %(column)s %(type)s NULL"
    sql_alter_column_not_null = "MODIFY %(column)s %(type)s NOT NULL"
    sql_alter_column_type = "MODIFY %(column)s %(type)s"
    sql_rename_column = "ALTER TABLE %(table)s CHANGE %(old_column)s %(new_column)s %(type)s"

    sql_delete_unique = "ALTER TABLE %(table)s DROP INDEX %(name)s"

    sql_create_fk = (
        "ALTER TABLE %(table)s ADD CONSTRAINT %(name)s FOREIGN KEY "
        "(%(column)s) REFERENCES %(to_table)s (%(to_column)s)"
    )
    sql_delete_fk = "ALTER TABLE %(table)s DROP FOREIGN KEY %(name)s"

    sql_delete_index = "DROP INDEX %(name)s ON %(table)s"

    sql_create_pk = "ALTER TABLE %(table)s ADD CONSTRAINT %(name)s PRIMARY KEY (%(columns)s)"
    sql_delete_pk = "ALTER TABLE %(table)s DROP PRIMARY KEY"
