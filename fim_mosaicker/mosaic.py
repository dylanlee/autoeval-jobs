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
    """Raster mosaicking using GDAL with gdalwarp.

    Parameters
    ----------
    raster_paths : list[str]
        List of paths to rasters to be mosaicked.
    output_path : str
        Path where to save the mosaicked output.
    clip_geometry : str or dict, optional
        Vector file path or GeoJSON-like geometry to clip the output raster.
    fim_type : str, optional
        Type of FIM output, either "depth" or "extent".
        For depth: uses float32 dtype and -9999 as nodata.
        For extent: uses uint8 dtype and 255 as nodata, converts all nonzero values to 1.
    memory_limit : int, optional
        Memory limit for GDAL processing in MB.

    Returns
    -------
    str
        Path to the output raster.
    """
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
        # For "extent" type - we need to handle each raster differently
        if fim_type == "extent":
            # First, convert each input raster to binary (0 or 1) format
            binary_rasters = []
            for i, raster_path in enumerate(raster_paths):
                binary_path = f"{output_path}.bin.{i}.tif"
                binary_rasters.append(binary_path)

                # Open source raster
                src_ds = gdal.Open(raster_path)
                if src_ds is None:
                    raise RuntimeError(f"Failed to open raster: {raster_path}")

                # Read data
                data = src_ds.GetRasterBand(1).ReadAsArray()
                src_nodata = src_ds.GetRasterBand(1).GetNoDataValue()

                # Create binary output
                driver = gdal.GetDriverByName("GTiff")
                dst_ds = driver.Create(
                    binary_path,
                    src_ds.RasterXSize,
                    src_ds.RasterYSize,
                    1,
                    gdal.GDT_Byte,
                    ["COMPRESS=LZW", "PREDICTOR=2", "TILED=YES"],
                )

                # Copy projection and geotransform
                dst_ds.SetGeoTransform(src_ds.GetGeoTransform())
                dst_ds.SetProjection(src_ds.GetProjection())
                dst_ds.GetRasterBand(1).SetNoDataValue(
                    255
                )  # Using 255 as nodata for binary

                # Convert to binary: 1 where data exists and is not 0, 0 for zeros, nodata elsewhere
                dst_ds.GetRasterBand(1).WriteArray(
                    np.where(data != src_nodata, 
                             np.where(data != 0, 1, 0),  # If not no 1 for non-zero, 0 for zero
                             255).astype(np.uint8)       # If no 255
                )

                # Cleanup
                src_ds = None
                dst_ds = None

            # Now mosaic the binary rasters with MAX resampling to preserve all 1s
            warp_options = gdal.WarpOptions(
                format="GTiff",
                srcNodata=255,
                dstNodata=255,
                creationOptions=["COMPRESS=LZW", "PREDICTOR=2", "TILED=YES"],
                outputType=gdal.GDT_Byte,
                warpMemoryLimit=memory_limit,
                resampleAlg="max",
                cutlineDSName=clip_file,
                cropToCutline=bool(clip_file),
            )

            # Perform the warp operation and ensure it completes
            ds = gdal.Warp(output_path, binary_rasters, options=warp_options)
            if ds is None:
                raise RuntimeError("Failed to create mosaic")

            # Explicitly flush and close the dataset to ensure data is written
            ds.FlushCache()
            ds = None  # Close dataset

            # Verify the output file exists and has valid size
            if not os.path.exists(output_path):
                raise RuntimeError(f"Output file was not created: {output_path}")
            if os.path.getsize(output_path) == 0:
                raise RuntimeError(f"Output file is empty: {output_path}")

            # Clean up temporary binary rasters
            for binary_path in binary_rasters:
                if os.path.exists(binary_path):
                    os.remove(binary_path)

            return output_path

        else:  # For depth type, directly warp to output
            warp_options = gdal.WarpOptions(
                format="GTiff",
                srcNodata=nodata,
                dstNodata=nodata,
                creationOptions=["COMPRESS=LZW", "PREDICTOR=2", "TILED=YES"],
                outputType=gdal_dtype,
                warpMemoryLimit=memory_limit,
                resampleAlg="max",
                cutlineDSName=clip_file,
                cropToCutline=bool(clip_file),
            )

            # Perform the warp operation and ensure it completes
            ds = gdal.Warp(output_path, raster_paths, options=warp_options)
            if ds is None:
                raise RuntimeError("Failed to create mosaic")

            # Explicitly flush and close the dataset to ensure data is written
            ds.FlushCache()
            ds = None  # Close dataset

            # Verify the output file exists and has valid size
            if not os.path.exists(output_path):
                raise RuntimeError(f"Output file was not created: {output_path}")
            if os.path.getsize(output_path) == 0:
                raise RuntimeError(f"Output file is empty: {output_path}")

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
