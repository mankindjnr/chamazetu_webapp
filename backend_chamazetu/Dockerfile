FROM python:3.10.12
RUN apt-get update && apt-get install -y tzdata
ENV TZ=Africa/Nairobi
# Set the working directory in the container
WORKDIR /app/backend

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN pip install --upgrade pip
COPY ./requirements.txt /app/backend/requirements.txt
# Install the dependencies
RUN pip install -r requirements.txt

# Copy the content of the local src directory to the working directory
COPY . /app/backend

# Command to run on container start
# CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9400", "--reload"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9400", "--workers", "4"]