FROM python:3.10.12

# Set the working directory in the container
WORKDIR /usr/src/djangofrontend

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN pip install --upgrade pip
COPY ./requirements.txt /usr/src/djangofrontend/requirements.txt
# Install the dependencies
RUN pip install -r requirements.txt

# Copy the content of the local src directory to the working directory
COPY . /usr/src/djangofrontend/

# Install wait-for-it
# ADD https://github.com/eficode/wait-for/raw/master/wait-for /wait-for
# RUN chmod +x /wait-for
# without migrating the db i can skip the wait-for-it - i'll migrate the db manually in the container

RUN python manage.py collectstatic --no-input

# RUN python manage.py migrate

# Command to run on container start
CMD [ "python", "manage.py", "runserver", "0.0.0.0:8000" ]

# Use wait-for-it to delay execution until db is ready
# CMD /wait-for chamazetu_backend:5432 -- python manage.py migrate && python manage.py runserver 0.0.0.0:8000
# withuot migrate i can skip the wait-for-it
# CMD /wait-for chamazetu_backend:5432 -- python manage.py runserver 0.0.0.0:8000