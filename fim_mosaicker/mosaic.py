import os
import sys
import json
from typing import Union, Optional, Literal
from pathlib import Path
from osgeo import gdal
import numpy as np


def mosaic_rasters(
    raster_paths: list[str],
    output_path: str,
    clip_geometry: Optional[Union[str, dict]] = None,
    fim_type: Literal["depth", "extent"] = "depth",
    memory_limit: int = 512,
) -> str:
    """Raster mosaicking using GDAL with pixelwise maximum and memory limits."""
    if not raster_paths:
        raise ValueError("No rasters provided for mosaicking.")

    # Setup
    gdal.UseExceptions()
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Set parameters based on fim_type
    nodata = -9999 if fim_type == "depth" else 255
    gdal_dtype = gdal.GDT_Float32 if fim_type == "depth" else gdal.GDT_Byte

    # Handle clip geometry if provided
    temp_json = None
    clip_file = None
    if clip_geometry:
        if isinstance(clip_geometry, dict):
            temp_json = f"{output_path}.temp.json"
            with open(temp_json, "w") as f:
                json.dump(clip_geometry, f)
            clip_file = temp_json
        else:
            clip_file = clip_geometry

    try:
        # For "extent" type, convert each raster to binary format first
        if fim_type == "extent":
            binary_rasters = []
            for i, raster_path in enumerate(raster_paths):
                binary_path = f"{output_path}.bin.{i}.tif"
                binary_rasters.append(binary_path)
                
                # Process in blocks to respect memory limits
                src_ds = gdal.Open(raster_path)
                if src_ds is None:
                    raise RuntimeError(f"Failed to open raster: {raster_path}")
                
                # Get raster dimensions and block size
                xsize = src_ds.RasterXSize
                ysize = src_ds.RasterYSize
                band = src_ds.GetRasterBand(1)
                src_nodata = band.GetNoDataValue()
                
                # Calculate optimal block size based on memory limit
                # Assuming 4 bytes per pixel (float32)
                bytes_per_pixel = 4 if fim_type == "depth" else 1
                max_pixels = (memory_limit * 1024 * 1024) // bytes_per_pixel
                
                # Get the block size from the raster if available
                block_xsize, block_ysize = band.GetBlockSize()
                if block_xsize == xsize:  # If raster is not tiled
                    # Calculate a reasonable block size
                    block_ysize = min(512, ysize)
                    block_xsize = min(int(max_pixels / block_ysize), xsize)
                
                # Create output binary raster
                driver = gdal.GetDriverByName("GTiff")
                dst_ds = driver.Create(
                    binary_path,
                    xsize,
                    ysize,
                    1,
                    gdal.GDT_Byte,
                    ["COMPRESS=LZW", "PREDICTOR=2", "TILED=YES"],
                )
                
                # Copy projection and geotransform
                dst_ds.SetGeoTransform(src_ds.GetGeoTransform())
                dst_ds.SetProjection(src_ds.GetProjection())
                dst_ds.GetRasterBand(1).SetNoDataValue(255)
                
                # Process the raster in blocks
                for y in range(0, ysize, block_ysize):
                    actual_block_ysize = min(block_ysize, ysize - y)
                    for x in range(0, xsize, block_xsize):
                        actual_block_xsize = min(block_xsize, xsize - x)
                        
                        # Read block data
                        data = band.ReadAsArray(x, y, actual_block_xsize, actual_block_ysize)
                        
                        # Convert to binary: 1 where data exists and is not 0, 0 for zeros, nodata elsewhere
                        binary_data = np.where(
                            data != src_nodata,
                            np.where(data != 0, 1, 0),
                            255
                        ).astype(np.uint8)
                        
                        # Write block to output
                        dst_ds.GetRasterBand(1).WriteArray(binary_data, x, y)
                
                # Cleanup
                src_ds = None
                dst_ds = None
            
            # Use the binary rasters for mosaicking
            input_rasters = binary_rasters
        else:
            # For depth type, use original rasters
            input_rasters = raster_paths
        
        # Create a VRT from all input rasters
        vrt_path = f"{output_path}.vrt"
        vrt_options = gdal.BuildVRTOptions(
            resolution='highest',
            separate=False,
            srcNodata=255 if fim_type == "extent" else None,
            VRTNodata=nodata,
        )
        
        vrt_ds = gdal.BuildVRT(vrt_path, input_rasters, options=vrt_options)
        vrt_ds.FlushCache()
        vrt_ds = None
        
        # Use gdal.Warp with max resampling and memory limit
        warp_options = gdal.WarpOptions(
            format="GTiff",
            srcNodata=nodata,
            dstNodata=nodata,
            multithread=True,
            warpMemoryLimit=memory_limit,
            creationOptions=["COMPRESS=LZW", "PREDICTOR=2", "TILED=YES"],
            resampleAlg="max",  # Use max resampling
            callback=gdal.TermProgress_nocb,
            cutlineDSName=clip_file,
            cropToCutline=bool(clip_file),
        )
        
        gdal.Warp(output_path, vrt_path, options=warp_options)
        
        # Clean up VRT
        if os.path.exists(vrt_path):
            os.remove(vrt_path)
        
        # Clean up temporary binary rasters
        if fim_type == "extent":
            for binary_path in binary_rasters:
                if os.path.exists(binary_path):
                    os.remove(binary_path)
        
        return output_path
        
    except Exception as e:
        if os.path.exists(output_path):
            os.remove(output_path)
        raise RuntimeError(f"Error during mosaic processing: {str(e)}")
    
    finally:
        if temp_json and os.path.exists(temp_json):
            os.remove(temp_json)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Mosaic multiple rasters with optional clipping.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "raster_paths",
        nargs="+",
        type=Path,
        help="Paths to the input rasters to be mosaicked",
    )
    parser.add_argument(
        "output_path", type=Path, help="Path where to save the mosaicked output"
    )
    parser.add_argument(
        "--clip-geometry",
        type=Path,
        help="Optional path to vector file for clipping the output",
    )
    parser.add_argument(
        "--fim-type",
        choices=["depth", "extent"],
        default="depth",
        help="Type of FIM output (affects data type and nodata value)",
    )
    parser.add_argument(
        "--memory-limit",
        type=int,
        default=512,
        help="Memory limit for GDAL processing in MB",
    )

    args = parser.parse_args()

    try:
        output_raster = mosaic_rasters(
            raster_paths=[str(p) for p in args.raster_paths],
            output_path=str(args.output_path),
            clip_geometry=str(args.clip_geometry) if args.clip_geometry else None,
            fim_type=args.fim_type,
            memory_limit=args.memory_limit,
        )
        print(f"Successfully created mosaic: {output_raster}")
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)
