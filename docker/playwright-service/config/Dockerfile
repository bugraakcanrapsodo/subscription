FROM mcr.microsoft.com/playwright:v1.56.1-noble

# Combine all system package installations in one layer to improve caching
# Using --no-install-recommends reduces package size
# Cleaning up in the same RUN command reduces layer size
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        xvfb \
        curl \
        wget \
        gnupg \
        iputils-ping \
        iproute2 \
        ca-certificates \
        ffmpeg && \
    curl -fsSLo /usr/share/keyrings/mullvad-keyring.asc https://repository.mullvad.net/deb/mullvad-keyring.asc && \
    echo "deb [signed-by=/usr/share/keyrings/mullvad-keyring.asc arch=$(dpkg --print-architecture)] https://repository.mullvad.net/deb/stable stable main" > /etc/apt/sources.list.d/mullvad.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends mullvad-vpn && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

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


