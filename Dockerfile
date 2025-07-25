# Use Ubuntu as base image for better Chrome support
FROM ubuntu:22.04

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV DISPLAY=:99
ENV CHROME_BIN=/usr/bin/google-chrome-stable
ENV CHROMEDRIVER_DIR=/usr/local/bin
# Disable Redis by default since it's not included in this container
# Set DISABLE_REDIS=false and provide REDIS_URL if you have external Redis
ENV DISABLE_REDIS=true
# Default app base URL - override with your deployment URL
ENV APP_BASE_URL=https://midas-portal-f853.vercel.app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    wget \
    gnupg \
    unzip \
    curl \
    xvfb \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libdrm2 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    xdg-utils \
    libu2f-udev \
    libvulkan1 \
    && rm -rf /var/lib/apt/lists/*

# Install Google Chrome
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Install ChromeDriver using the new Chrome for Testing API
RUN CHROME_VERSION=$(google-chrome --version | cut -d " " -f3) \
    && echo "Chrome version: $CHROME_VERSION" \
    && MAJOR_VERSION=$(echo $CHROME_VERSION | cut -d "." -f1) \
    && echo "Chrome major version: $MAJOR_VERSION" \
    && if [ "$MAJOR_VERSION" -ge "115" ]; then \
        # For Chrome 115+, use Chrome for Testing API
        CHROMEDRIVER_URL=$(curl -s "https://googlechromelabs.github.io/chrome-for-testing/latest-versions-per-milestone-with-downloads.json" \
            | python3 -c "import sys, json; data=json.load(sys.stdin); print(data['milestones']['$MAJOR_VERSION']['downloads']['chromedriver'][0]['url'] if '$MAJOR_VERSION' in data['milestones'] and 'chromedriver' in data['milestones']['$MAJOR_VERSION']['downloads'] else '')") \
        && if [ -n "$CHROMEDRIVER_URL" ]; then \
            echo "Downloading ChromeDriver from: $CHROMEDRIVER_URL"; \
            wget -O /tmp/chromedriver.zip "$CHROMEDRIVER_URL"; \
        else \
            echo "Using latest stable ChromeDriver"; \
            wget -O /tmp/chromedriver.zip "https://storage.googleapis.com/chrome-for-testing-public/$(curl -s https://googlechromelabs.github.io/chrome-for-testing/LATEST_RELEASE_STABLE)/linux64/chromedriver-linux64.zip"; \
        fi; \
    else \
        # Fallback for older Chrome versions
        CHROMEDRIVER_VERSION=$(curl -s "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_${MAJOR_VERSION}") \
        && wget -O /tmp/chromedriver.zip "https://chromedriver.storage.googleapis.com/${CHROMEDRIVER_VERSION}/chromedriver_linux64.zip"; \
    fi \
    && unzip /tmp/chromedriver.zip -d /tmp/ \
    && find /tmp -name "chromedriver*" -type f -executable -exec mv {} ${CHROMEDRIVER_DIR}/chromedriver \; \
    && chmod +x ${CHROMEDRIVER_DIR}/chromedriver \
    && rm /tmp/chromedriver.zip \
    && rm -rf /tmp/chromedriver* \
    && ${CHROMEDRIVER_DIR}/chromedriver --version

# Set working directory
WORKDIR /app

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user for security
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose port for web service
EXPOSE 8080

# Health check for Render deployment
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Start the web service (auto-starts Gmail workflow in background if GMAIL_PASSWORD is provided)
CMD ["python3", "web_service.py"] 