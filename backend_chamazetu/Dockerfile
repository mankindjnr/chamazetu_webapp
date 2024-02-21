FROM python:3.10.12

# Set the working directory in the container
WORKDIR /usr/src/fastbackend

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN pip install --upgrade pip
COPY ./requirements.txt /usr/src/fastbackend/requirements.txt
# Install the dependencies
RUN pip install -r requirements.txt

# Copy the content of the local src directory to the working directory
COPY . /usr/src/fastbackend

# Command to run on container start
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9400", "--reload"]