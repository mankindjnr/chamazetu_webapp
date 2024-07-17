FROM python:3.10.12
RUN apt-get update && apt-get install -y tzdata
ENV TZ=Africa/Nairobi
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

EXPOSE 8000

CMD python manage.py runserver 0.0.0.0:8000
