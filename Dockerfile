# Use the base image
FROM tiangolo/uvicorn-gunicorn-fastapi:python3.11

# Set the working directory
WORKDIR /app

# Copy the requirements file first to leverage Docker's caching mechanism
COPY requirements.txt /app/

# Install the dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY src /app/

# Expose the port (if necessary)
EXPOSE 6010

# Command to run the FastAPI app using Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "6010", "--reload"]
