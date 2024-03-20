The output from `docker-compose ps` shows that your Redis service (message_broker) is up and running, and the port mapping is correct (host port 6380 is mapped to container port 6379).

However, the Celery worker service is trying to connect to `redis://message_broker:6380`, which is incorrect. Within the Docker network, services communicate with each other using the internal ports, not the mapped host ports.

So, the Celery worker should connect to `redis://message_broker:6379`, not `redis://message_broker:6380`.

Please update the `CELERY_BROKER_URL` in your Celery worker configuration to `redis://message_broker:6379`.

---

---

The warning message suggests that you're using a deprecated configuration setting `broker_connection_retry` in your Celery configuration. This setting will no longer be used to determine whether broker connection retries are made during startup in Celery 6.0 and above.

To fix this warning, you should add a new configuration setting `broker_connection_retry_on_startup` and set it to `True` if you want to retain the existing behavior for retrying connections on startup.

Here's how you can update your Celery configuration:

```python
broker_connection_retry_on_startup = True
```

Also, it's recommended to run the `celery upgrade settings` command to upgrade your settings for a smoother transition to Celery 6.0. You can run this command in your terminal:

```sh
celery upgrade settings path/to/settings.py
```

Replace `path/to/settings.py` with the actual path to your Celery settings file.
