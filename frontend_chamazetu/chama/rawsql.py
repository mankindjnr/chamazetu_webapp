from django.db import connection

# fetchall will return all rows from the query result as a list of tuples
# this function is flexible and can be used to execute any sql query


def execute_sql(sql, params):
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        result = cursor.fetchall()
    return result
