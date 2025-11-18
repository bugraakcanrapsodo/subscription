FROM mcr.microsoft.com/playwright:v1.56.1-noble

# Install Xvfb
RUN apt-get update && apt-get install -y xvfb && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create directories
RUN mkdir -p /app/output/screenshots /app/output/videos /app/output/logs && \
    chmod 777 /app/output/screenshots /app/output/videos /app/output/logs

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy application files
COPY src/ ./src/
COPY config/ ./config/
COPY scripts/ ./scripts/

# Expose the port
EXPOSE 3000

# Set up Xvfb and run the app
ENV DISPLAY=:99
# Suppress XKEYBOARD warnings by redirecting stderr to /dev/null
CMD Xvfb :99 -screen 0 1280x720x24 -ac 2>/dev/null & node src/app.js


