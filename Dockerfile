# Use the GDAL Ubuntu image directly
FROM ghcr.io/osgeo/gdal:ubuntu-small-3.10.2

# Create and set working directory
WORKDIR /app

# Copy requirements file
COPY requirements.txt ./

# Install Python pip and clean up
RUN apt-get update && \
    apt-get install -y --no-install-recommends python3-pip wget && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    rm /usr/lib/python3.*/EXTERNALLY-MANAGED

# Install Python dependencies from requirements.txt
RUN pip3 install -r requirements.txt && \
    rm requirements.txt
