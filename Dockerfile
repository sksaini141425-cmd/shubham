# Use Python 3.11 slim image
FROM python:3.11-slim

# Set the working directory
WORKDIR /app

# Copy project files
COPY . /app

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose port for the dashboard (Render assigns PORT env var)
EXPOSE 5000

# Start the bot (Flask dashboard + trading loop run in the same process)
CMD ["python", "main.py"]
