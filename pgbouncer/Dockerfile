# pgbouncer/Dockerfile
FROM pgbouncer/pgbouncer:latest

# Create a writable directory for configuration files in /tmp
RUN mkdir -p /tmp/pgbouncer

# Copy the configuration files to the writable directory
COPY pgbouncer.ini /tmp/pgbouncer/pgbouncer.ini
COPY userlist.txt /tmp/pgbouncer/userlist.txt

# Entrypoint to start pgbouncer using the configuration files in /tmp/pgbouncer
ENTRYPOINT ["/opt/pgbouncer/entrypoint.sh", "/tmp/pgbouncer/pgbouncer.ini"]
