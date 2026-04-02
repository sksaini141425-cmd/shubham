# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Set default environment variables (can be overridden in the cloud dashboard)
ENV STRATEGY="multitimeframe"
ENV LEVERAGE="3"
ENV MAX_TRADES="3"
ENV PORT="5000"
ENV USE_REAL_EXCHANGE="false"

# Expose the dashboard port
EXPOSE 5000

# Run the bot with recommended cloud settings
# Note: We use main.py directly. Environment variables should be set in the cloud provider UI.
CMD ["sh", "-c", "python main.py --port $PORT --strategy $STRATEGY --leverage $LEVERAGE --max_trades $MAX_TRADES"]
