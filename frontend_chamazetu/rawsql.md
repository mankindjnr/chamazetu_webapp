# DJANGO-RAW-SQL-QUERIES

To configure raw sql queries in django, you need to do the following:

1. install psycopg2-binary

```bash
pip install psycopg2-binary
```

2. configure the database in settings.py

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'chamadb',
        'USER': 'mankind',
        'PASSWORD': 'MhF,y38(p2(b-',
        'HOST': 'chamazetu_database',
        'PORT': '5432',
    }
}
```

The database is hosted in a docker container. The host is the name of the container/service name.

3. Create a function to execute the raw sql queries

```python
import psycopg2
from django.conf import settings

def execute_raw_sql_query(query):
    conn = psycopg2.connect(
        dbname=settings.DATABASES['default']['NAME'],
        user=settings.DATABASES['default']['USER'],
        password=settings.DATABASES['default']['PASSWORD'],
        host=settings.DATABASES['default']['HOST'],
        port=settings.DATABASES['default']['PORT']
    )
    cur = conn.cursor()
    cur.execute(query)
    result = cur.fetchall()
    conn.commit()
    cur.close()
    conn.close()
    return result
```

or

    ```python
    from django.db import connection

    def execute_raw_sql_query(query):
        with connection.cursor() as cursor:
            cursor.execute(query)
            result = cursor.fetchall()
        return result
    ```

or

    ```python
    from django.db import connection

    def execute_raw_sql_query():
        with connection.cursor() as cursor:
            cursor.execute('SELECT * FROM myapp_person')
            row = cursor.fetchone()
        return row
    ```

Its a best practice to use parameterized queries to prevent sql injection attacks.

---

4. parameterized queries

   ```python
   from django.db import connection

   def execute_raw_sql_query(query, params):
       with connection.cursor() as cursor:
           cursor.execute(query, params)
           result = cursor.fetchall()
       return result
   ```

   # Usage

   ```python
   query = 'SELECT * FROM myapp_person WHERE last_name = %s'
   params = ('Smith',)
   result = execute_raw_sql_query(query, params)
   ```

   The placeholder `%s` is used to pass parameters to the query. It is used for all data types not just strings.

---
