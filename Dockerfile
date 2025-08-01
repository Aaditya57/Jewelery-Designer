# Use an official Python runtime as a parent image
FROM python:3.9-slim-buster

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container at /app
COPY . .

# Expose port 5000 (where Flask runs)
EXPOSE 5000

# Run the Flask application
# Use gunicorn for production, but for dev, direct flask run is fine.
# For production, you'd typically use: CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]
CMD ["python", "app.py"]