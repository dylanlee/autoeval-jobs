import rasterio
from rasterio.merge import merge
from rasterio.windows import Window
from rasterio.mask import mask
import numpy as np
from typing import Union, Optional, Literal
import os
import sys
import fiona


def mosaic_rasters(
    raster_paths: list[str],
    output_path: str,
    clip_geometry: Optional[Union[str, dict]] = None,
    fim_type: Literal["depth", "extent"] = "depth",
    window_size: int = 256,
) -> str:
    """Raster mosaicking using rasterio with block processing.

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
    window_size : int, optional
        Size of the processing window in pixels.

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
    if window_size <= 0:
        raise ValueError("window_size must be positive")

    if fim_type not in ["depth", "extent"]:
        raise ValueError("fim_type must be either 'depth' or 'extent'")

    if not raster_paths:
        raise ValueError("No rasters provided for mosaicking.")

    # Set raster properties based on fim_type
    if fim_type == "depth":
        nodata = -9999
        dtype = "float32"
    else:  # extent
        nodata = 255
        dtype = "uint8"

    # Open all rasters and get their metadata
    src_files = []
    try:
        for path in raster_paths:
            src = rasterio.open(path)
            src_files.append(src)

        # Check that all rasters have the same CRS
        crs = src_files[0].crs
        if not all(src.crs == crs for src in src_files):
            raise ValueError("All rasters must have the same CRS")

        # Get bounds of the mosaic
        bounds = [src.bounds for src in src_files]
        left = min(bound.left for bound in bounds)
        bottom = min(bound.bottom for bound in bounds)
        right = max(bound.right for bound in bounds)
        top = max(bound.top for bound in bounds)

        # Get resolution (assuming all rasters have same resolution)
        res = src_files[0].res
        if not all(src.res == res for src in src_files):
            raise ValueError("All rasters must have the same resolution")

        # Calculate output dimensions
        width = int((right - left) / res[0] + 0.5)
        height = int((top - bottom) / res[1] + 0.5)

        # Create output profile
        profile = src_files[0].profile.copy()
        profile.update(
            {
                "driver": "GTiff",
                "height": height,
                "width": width,
                "transform": rasterio.transform.from_bounds(
                    left, bottom, right, top, width, height
                ),
                "dtype": dtype,
                "nodata": nodata,
                "tiled": True,
                "compress": "lzw",
                "predictor": 2,
            }
        )

        # Create output raster
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with rasterio.open(output_path, "w", **profile) as dst:
            # Process by blocks
            for y in range(0, height, window_size):
                y_size = min(window_size, height - y)
                for x in range(0, width, window_size):
                    x_size = min(window_size, width - x)

                    window = Window(x, y, x_size, y_size)
                    window_transform = dst.window_transform(window)

                    # Initialize output block
                    out_data = np.full((y_size, x_size), nodata, dtype=profile["dtype"])

                    # Read and merge data from each source that overlaps this window
                    for src in src_files:
                        # Check if source overlaps with window
                        src_window = src.window(
                            *rasterio.windows.from_bounds(
                                *rasterio.transform.array_bounds(
                                    y_size, x_size, window_transform
                                ),
                                src.transform,
                            )
                        )

                        if src_window.width <= 0 or src_window.height <= 0:
                            continue

                        data = src.read(1, window=src_window)
                        if data is None or data.size == 0:
                            continue

                        # For extent type, convert nonzero values to 1
                        if fim_type == "extent":
                            data = (data != 0).astype(np.uint8)

                        # Update output with maximum values
                        valid_mask = (
                            data != src.nodata
                            if src.nodata is not None
                            else np.ones_like(data, dtype=bool)
                        )
                        np.maximum(
                            out_data, np.where(valid_mask, data, nodata), out=out_data
                        )

                    # Write block
                    dst.write(out_data, window=window, indexes=1)

        # Apply clipping if geometry provided
        if clip_geometry is not None:
            with rasterio.open(output_path, "r+") as src:
                if isinstance(clip_geometry, str):
                    with fiona.open(clip_geometry, "r") as clip_file:
                        geoms = [feature["geometry"] for feature in clip_file]
                else:
                    geoms = (
                        [clip_geometry]
                        if isinstance(clip_geometry, dict)
                        else clip_geometry
                    )

                out_data, out_transform = mask(src, geoms, crop=False, nodata=nodata)
                src.write(out_data[0], indexes=1)

    finally:
        # Close all source files
        for src in src_files:
            src.close()

    return output_path


if __name__ == "__main__":
    import argparse
    from pathlib import Path

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
        "--window-size",
        type=int,
        default=256,
        help="Size of the processing window in pixels",
    )

    args = parser.parse_args()

    try:
        # Convert Path objects to strings for the main function
        output_raster = mosaic_rasters(
            raster_paths=[str(p) for p in args.raster_paths],
            output_path=str(args.output_path),
            clip_geometry=str(args.clip_geometry) if args.clip_geometry else None,
            fim_type=args.fim_type,
            window_size=args.window_size,
        )
        print(f"Successfully created mosaic: {output_raster}")

    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)
