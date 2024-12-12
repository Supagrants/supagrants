FROM tiangolo/uvicorn-gunicorn-fastapi:python3.11
# Set the working directory to /app
WORKDIR /app

# Copy the current directory contents into the container at /app
ADD requirements.txt /app

RUN pip3 install -r requirements.txt

COPY src /app