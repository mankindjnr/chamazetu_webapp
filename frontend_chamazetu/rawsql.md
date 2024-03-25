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

# some best practices for optimizing Django template rendering performance

1. **Minimize Database Queries**: Try to fetch all the data you need in as few database queries as possible. Use Django's `select_related` and `prefetch_related` methods to reduce the number of database hits.

2. **Use Pagination**: If you're displaying a lot of data, consider using pagination to split the data into manageable chunks. Django provides a built-in Pagination class that makes this easy.

3. **Cache Expensive Queries**: If you have some expensive database queries that don't change often, consider caching the results. Django provides a robust cache framework that can cache data at various levels.

4. **Avoid Complex Computations in Templates**: Templates are meant for presentation, not for business logic. Try to do any complex computations in your views or models, not in your templates.

5. **Use `{% include %}` with caution**: The `{% include %}` tag can be useful for reusing templates, but it can also slow down rendering if overused. Each `{% include %}` results in an additional disk access.

6. **Use `{% block %}` and `{% extends %}` for Template Inheritance**: This allows you to reuse base templates, which can significantly reduce the amount of HTML you need to write.

7. **Minimize Use of `{% with %}` Tag**: The `{% with %}` tag can slow down template rendering, especially if used in a loop. Try to pass variables directly to the template context instead.

8. **Use Django Compressor for Static Files**: Django Compressor can combine and minify your CSS and JavaScript files, reducing the number of HTTP requests and the amount of data that needs to be transferred.

9. **Use `{% spaceless %}` Tag**: This tag removes whitespace between HTML tags, which can reduce the size of the rendered HTML.

10. **Keep Templates Small and Simple**: The more complex your templates, the slower they will render. Try to keep your templates as simple as possible.
