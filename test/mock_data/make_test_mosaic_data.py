from osgeo import gdal, osr
import numpy as np

# Configuration
output_files = ["raster1.tif", "raster2.tif", "raster3.tif", "raster4.tif"]
nodata_values = [255, 254, 253, 252]  # Different nodata for each raster
corner_tiles = [
    {"row": (0, 256), "col": (0, 256)},  # Top-left corner
    {"row": (0, 256), "col": (512, 768)},  # Top-right corner
    {"row": (512, 768), "col": (0, 256)},  # Bottom-left corner
    {"row": (512, 768), "col": (512, 768)},  # Bottom-right corner
]

# Define spatial reference system (using WGS 84 as an example)
srs = osr.SpatialReference()
srs.ImportFromEPSG(4326)  # WGS 84

# Define geotransform parameters
# Format: (top_left_x, pixel_width, rotation, top_left_y, rotation, pixel_height)
# Example: Starting at longitude 0, latitude 45, with 0.001-degree pixel size
x_min = 0.0
y_max = 45.0
pixel_size = 0.001  # approximately 111 meters at the equator
geotransform = (x_min, pixel_size, 0, y_max, 0, -pixel_size)

for i in range(4):
    # Create a 768x768 array initialized with zeros
    data = np.zeros((768, 768), dtype=np.uint8)

    # Set the center tile to nodata
    data[256:512, 256:512] = nodata_values[i]

    # Set the designated corner to 1
    corner = corner_tiles[i]
    data[corner["row"][0] : corner["row"][1], corner["col"][0] : corner["col"][1]] = 1

    # Create the GeoTIFF with 256x256 tiling
    driver = gdal.GetDriverByName("GTiff")
    ds = driver.Create(
        output_files[i],
        768,
        768,
        1,
        gdal.GDT_Byte,
        options=["TILED=YES", "BLOCKXSIZE=256", "BLOCKYSIZE=256"],
    )

    # Set the geotransform and spatial reference
    ds.SetGeoTransform(geotransform)
    ds.SetProjection(srs.ExportToWkt())

    # Write data and set nodata value
    ds.GetRasterBand(1).WriteArray(data)
    ds.GetRasterBand(1).SetNoDataValue(nodata_values[i])

    # Close the dataset
    ds = None

print("Georeferenced datasets created successfully.")
