# Use the GDAL Ubuntu image directly
FROM ghcr.io/osgeo/gdal:ubuntu-small-3.10.2

# Create and set working directory
WORKDIR /app

# Install Python packages via apt
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-pip \
    python3-numpy \
    python3-pandas \
    python3-dateutil \
    python3-boto3 \
    python3-click \
    python3-fiona \
    python3-rasterio \
    python3-six \
    python3-urllib3 \
    python3-wrapt \
    python3-jmespath \
    python3-pyparsing \
    python3-smart-open \
    wget \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
