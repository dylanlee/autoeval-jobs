# Use the GDAL Ubuntu image directly
FROM ghcr.io/osgeo/gdal:ubuntu-small-3.10.2

# Install Python, pip, and venv
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-dev \
    python3-venv \
    && rm -rf /var/lib/apt/lists/*

# Create and set working directory
WORKDIR /app

# Get GDAL version and set as environment variable
RUN export GDAL_VERSION=$(gdal-config --version) && \
    echo "GDAL_VERSION=$GDAL_VERSION" >> /etc/environment

# Create a virtual environment
RUN python3 -m venv /app/venv --system-site-packages

# Use the virtual environment
ENV PATH="/app/venv/bin:$PATH"

# Copy requirements and install Python dependencies
COPY requirements.txt .

# Install Python dependencies in the virtual environment
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY fim_mosaicker/ fim_mosaicker/
COPY hand_inundator/ hand_inundator/
COPY test/ test/

# Create mock_data directory for tests
RUN mkdir -p test/mock_data/
