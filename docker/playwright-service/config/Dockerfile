FROM mcr.microsoft.com/playwright:v1.57.0-noble

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

# Create output directories
RUN mkdir -p /app/output/screenshots /app/output/videos /app/output/logs /app/output/attachments && \
    chmod 777 /app/output/screenshots /app/output/videos /app/output/logs /app/output/attachments

# Copy package files FIRST - this layer only rebuilds if package.json changes
# This is key for fast rebuilds during development
COPY package*.json ./

# Install npm dependencies
# Using npm install since package-lock.json doesn't exist
# --no-audit skips security audit (run separately if needed)
RUN npm install --no-audit

# Copy application files LAST - they change most frequently
# Docker will reuse cached layers above if only these files change
COPY src/ ./src/
COPY config/ ./config/
COPY scripts/ ./scripts/

# Expose the port
EXPOSE 3000

# Set up environment and run command
ENV DISPLAY=:99

# Start Mullvad daemon, Xvfb, and Node.js app
# The daemon needs to run in the background for Mullvad CLI commands to work
CMD mullvad-daemon & sleep 2 && Xvfb :99 -screen 0 1280x720x24 -ac 2>/dev/null & node src/app.js
