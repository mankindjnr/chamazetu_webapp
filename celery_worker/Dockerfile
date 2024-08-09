FROM python:3.10.12
RUN apt-get update && apt-get install -y tzdata
ENV TZ=Africa/Nairobi
# Set the working directory in the container
WORKDIR /app/celery

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN pip install --upgrade pip
COPY /frontend_chamazetu/requirements.txt /app/celery/requirements.txt
# Install the dependencies
RUN pip install --no-cache-dir -r requirements.txt

# add a non-root user
RUN useradd -ms /bin/bash frontenduser

# Copy the content of the local src directory to the working directory
COPY /frontend_chamazetu /app/celery

# Change the ownership of the working directory to the newly created user
RUN chown -R frontenduser:frontenduser /app/celery

# switch to the newly created user
USER frontenduser

# Run the application
CMD ["celery", "-A", "frontend_chamazetu.celery", "worker", "--loglevel=info"]