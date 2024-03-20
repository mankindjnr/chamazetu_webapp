FROM python:3.10.12

# Set the working directory in the container
WORKDIR /app/frontend

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN pip install --upgrade pip
COPY ./requirements.txt /app/frontend/requirements.txt
# Install the dependencies
RUN pip install -r requirements.txt

# Copy the content of the local src directory to the working directory
COPY . /app/frontend/

RUN python manage.py collectstatic --no-input

COPY ./cert.pem /app/frontend/certs
COPY ./key.pem /app/frontend/certs

EXPOSE 443

# create a new user "appuser" and switch to it
# RUN addgroup --system app && adduser --system --group app
# USER app

# Ensure that the certificates directory exists
# RUN mkdir -p /app/frontend/certs

# Copy certificate and key files to the container
# COPY ./cert.pem /app/frontend/certs/
# COPY ./key.pem /app/frontend/certs/

# # Adjust permissions for the certificate and key files
# RUN chown -R app:app /app/frontend/certs
# RUN chmod 600 /app/frontend/certs/*

#CMD /wait-for chamazetu_database:5432 -- python manage.py runsslserver --certificate /app/frontend/certs/cert.pem --key /app/frontend/certs/key.pem 0.0.0.0:8000
CMD python manage.py runsslserver --certificate /app/frontend/certs/cert.pem --key /app/frontend/certs/key.pem 0.0.0.0:8000
