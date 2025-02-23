from osgeo import gdal, ogr, osr
import pandas as pd
import numpy as np
import os
from typing import Union, Optional


def mosaic_rasters(
    raster_df: pd.DataFrame,
    output_path: str,
    mosaic_attribute: str = "inundation_rasters",
    mask: Optional[Union[str, ogr.Layer]] = None,
    nodata: Union[int, float] = -9999,
    block_size: int = 256,
    compress: bool = True,
) -> str:
    """Simple raster mosaicking using GDAL and OGR with memory-efficient block processing.

    Parameters
    ----------
    raster_df : pd.DataFrame
        DataFrame containing paths to rasters.
    output_path : str
        Path where to save the mosaicked output.
    mosaic_attribute : str
        Column name in DataFrame containing raster paths.
    mask : str or ogr.Layer, optional
        Vector mask file path or OGR Layer.
    nodata : int or float, optional
        NoData value for output raster.
    block_size : int, optional
        Size of blocks for processing.
    compress : bool, optional
        Whether to compress the output raster using LZW compression.

    Returns
    -------
    str
        Path to the output raster.

    Raises
    ------
    ValueError
        If input parameters are invalid or no rasters provided.
    RuntimeError
        If unable to open input files or process data.
    """
    # Validate inputs
    if block_size <= 0:
        raise ValueError("block_size must be positive")

    if mosaic_attribute not in raster_df.columns:
        raise ValueError(f"Column '{mosaic_attribute}' not found in DataFrame")

    raster_list = raster_df[mosaic_attribute].dropna().tolist()
    if len(raster_list) == 0:
        raise ValueError("No rasters provided for mosaicking.")

    # Get raster info and check projections
    raster_infos = []
    proj_ref = None
    base_res_x = None
    base_res_y = None

    try:
        for raster_path in raster_list:
            ds = gdal.Open(raster_path)
            if ds is None:
                raise RuntimeError(f"Cannot open {raster_path}")

            gt = ds.GetGeoTransform()
            proj = ds.GetProjection()
            x_size = ds.RasterXSize
            y_size = ds.RasterYSize
            x_min = gt[0]
            x_max = x_min + (gt[1] * x_size)
            y_min = gt[3] + (gt[5] * y_size)
            y_max = gt[3]
            res_x = gt[1]
            res_y = gt[5]

            # Validate resolution
            if abs(res_x) < 1e-10 or abs(res_y) < 1e-10:
                raise ValueError(f"Invalid resolution in {raster_path}")

            # Check resolution consistency
            if base_res_x is None:
                base_res_x = res_x
                base_res_y = res_y
            elif not (np.isclose(res_x, base_res_x) and np.isclose(res_y, base_res_y)):
                raise ValueError("All rasters must have matching resolution")

            raster_infos.append(
                {
                    "ds": ds,
                    "x_min": x_min,
                    "x_max": x_max,
                    "y_min": y_min,
                    "y_max": y_max,
                    "res_x": res_x,
                    "res_y": res_y,
                    "proj": proj,
                    "gt": gt,
                }
            )

            if proj_ref is None:
                proj_ref = proj
            elif proj != proj_ref:
                raise ValueError("All rasters must have the same projection")

        # Determine the bounds of the output raster
        x_min = min(info["x_min"] for info in raster_infos)
        x_max = max(info["x_max"] for info in raster_infos)
        y_min = min(info["y_min"] for info in raster_infos)
        y_max = max(info["y_max"] for info in raster_infos)

        # Use resolution from the first raster
        res_x = raster_infos[0]["res_x"]
        res_y = raster_infos[0]["res_y"]
        if res_y > 0:
            res_y = -res_y

        # Compute the size of the output raster
        n_cols = int((x_max - x_min) / res_x + 0.5)
        n_rows = int((y_max - y_min) / abs(res_y) + 0.5)

        # Create the output raster
        driver = gdal.GetDriverByName("GTiff")
        creation_options = ["TILED=YES"]
        if compress:
            creation_options.extend(["COMPRESS=LZW", "PREDICTOR=2"])

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        out_ds = driver.Create(
            output_path, n_cols, n_rows, 1, gdal.GDT_Float32, options=creation_options
        )

        if out_ds is None:
            raise RuntimeError(f"Failed to create output raster: {output_path}")

        out_gt = (x_min, res_x, 0, y_max, 0, res_y)
        out_ds.SetGeoTransform(out_gt)
        out_ds.SetProjection(proj_ref)
        out_band = out_ds.GetRasterBand(1)
        out_band.SetNoDataValue(nodata)
        out_band.Fill(nodata)

        # Process by blocks
        for i in range(0, n_rows, block_size):
            rows_to_process = min(block_size, n_rows - i)
            for j in range(0, n_cols, block_size):
                cols_to_process = min(block_size, n_cols - j)

                # Initialize output block
                out_data = np.full(
                    (rows_to_process, cols_to_process), nodata, dtype=np.float32
                )

                # Compute georeferenced coordinates of the block
                x0 = x_min + j * res_x
                y0 = y_max + i * res_y
                x1 = x0 + cols_to_process * res_x
                y1 = y0 + rows_to_process * res_y

                # For each input raster
                for info in raster_infos:
                    ds = info["ds"]
                    gt = info["gt"]
                    band = ds.GetRasterBand(1)
                    nodata_in = band.GetNoDataValue()

                    # Compute overlap
                    rx_min = info["x_min"]
                    rx_max = info["x_max"]
                    ry_min = info["y_min"]
                    ry_max = info["y_max"]

                    # Check if there is any overlap
                    if x0 >= rx_max or x1 <= rx_min or y1 >= ry_max or y0 <= ry_min:
                        continue

                    # Compute intersection
                    ix0 = max(x0, rx_min)
                    ix1 = min(x1, rx_max)
                    iy0 = min(y0, ry_max)
                    iy1 = max(y1, ry_min)

                    # Compute pixel offsets in input raster
                    i_xoff = int((ix0 - rx_min) / info["res_x"] + 0.5)
                    i_yoff = int((ry_max - iy0) / abs(info["res_y"]) + 0.5)
                    i_xsize = int((ix1 - ix0) / info["res_x"] + 0.5)
                    i_ysize = int((iy0 - iy1) / abs(info["res_y"]) + 0.5)

                    # Read input data
                    in_data = band.ReadAsArray(i_xoff, i_yoff, i_xsize, i_ysize)
                    if in_data is None:
                        continue

                    # Prepare masks
                    valid_mask = in_data != nodata_in

                    # Compute pixel offsets in output raster block
                    o_xoff = int((ix0 - x0) / res_x + 0.5)
                    o_yoff = int((y1 - iy0) / abs(res_y) + 0.5)
                    o_xsize = in_data.shape[1]
                    o_ysize = in_data.shape[0]

                    # Extract corresponding area from output data
                    out_sub = out_data[
                        o_yoff : o_yoff + o_ysize, o_xoff : o_xoff + o_xsize
                    ]

                    # Update out_data with maximum values
                    np.maximum(
                        out_sub, np.where(valid_mask, in_data, nodata), out=out_sub
                    )

                # Write block to output raster
                out_band.WriteArray(out_data, xoff=j, yoff=i)
                out_band.FlushCache()

        # Apply mask if provided using block processing
        if mask is not None:
            try:
                # Open mask vector file or use provided layer
                if isinstance(mask, str):
                    mask_ds = ogr.Open(mask)
                    if mask_ds is None:
                        raise RuntimeError(f"Cannot open mask file: {mask}")
                    mask_layer = mask_ds.GetLayer()
                elif isinstance(mask, ogr.Layer):
                    mask_layer = mask
                else:
                    raise ValueError("Mask must be a file path or OGR Layer")

                # Create temporary raster in memory for the current block
                mem_driver = gdal.GetDriverByName("MEM")

                # Process mask by blocks
                for i in range(0, n_rows, block_size):
                    rows_to_process = min(block_size, n_rows - i)
                    for j in range(0, n_cols, block_size):
                        cols_to_process = min(block_size, n_cols - j)

                        # Create temporary raster for current block
                        mask_ds_temp = mem_driver.Create(
                            "", cols_to_process, rows_to_process, 1, gdal.GDT_Byte
                        )

                        # Set geotransform for current block
                        block_x_min = x_min + j * res_x
                        block_y_max = y_max + i * res_y
                        block_gt = (block_x_min, res_x, 0, block_y_max, 0, res_y)
                        mask_ds_temp.SetGeoTransform(block_gt)
                        mask_ds_temp.SetProjection(proj_ref)

                        # Rasterize mask for current block
                        mask_band = mask_ds_temp.GetRasterBand(1)
                        mask_band.Fill(0)
                        gdal.RasterizeLayer(
                            mask_ds_temp, [1], mask_layer, burn_values=[1]
                        )

                        # Read mask and output data for current block
                        mask_data = mask_band.ReadAsArray()
                        out_data = out_band.ReadAsArray(
                            j, i, cols_to_process, rows_to_process
                        )

                        # Apply mask to current block
                        out_data = np.where(mask_data == 1, out_data, nodata)

                        # Write masked data back
                        out_band.WriteArray(out_data, xoff=j, yoff=i)
                        out_band.FlushCache()

                        # Clean up temporary mask raster
                        mask_ds_temp = None

            finally:
                # Clean up mask resources
                if isinstance(mask, str) and "mask_ds" in locals():
                    mask_ds = None

    finally:
        # Clean up resources
        out_band = None
        out_ds = None
        for info in raster_infos:
            info["ds"] = None

    return output_path
