#!/usr/bin/env python3
import numpy as np
import pandas as pd
import rasterio
from rasterio.windows import Window
import boto3
from smart_open import open
import json
import os
import argparse
import pdb


def simple_inundate_catchment_data(
    catchment_data: dict,
    forecast_path: str,
    output_path: str,
    window_size: int = 1024,
) -> None:
    """Process inundation with windowed S3 access and S3 forecast loading."""
    # Configure AWS session
    session = boto3.Session()

    # Load forecast from S3
    with open(forecast_path, "r", transport_params={"session": session}) as f:
        forecast = pd.read_csv(
            f,
            names=["feature_id", *pd.read_csv(f, nrows=0).columns[1:]],
            dtype={"feature_id": int, "discharge": float},
        )

    # Load and process hydrology data with lake filtering
    hydro_table = pd.DataFrame(
        [
            {
                "HydroID": hydro_id,
                "feature_id": curve["nwm_feature_id"],
                "stage": stage,
                "discharge_cms": q,
                "lake_id": curve["lake_id"],
            }
            for hydro_id, curve in catchment_data["hydrotable_entries"].items()
            for stage, q in zip(curve["stage"], curve["discharge_cms"])
            if curve["lake_id"] == -999
        ]
    )
    # Merge with forecast and interpolate
    merged = hydro_table.merge(forecast, on="feature_id", how="inner")
    interpolated = (
        merged.groupby("HydroID")
        .apply(
            lambda g: np.interp(g["discharge"].iloc[0], g["discharge_cms"], g["stage"])
        )
        .to_dict()
    )

    # Prepare raster processing
    rem_path = catchment_data["raster_pair"]["rem_raster_path"]
    catchment_path = catchment_data["raster_pair"]["catchment_raster_path"]

    # Download rasters from S3 if needed
    if rem_path.startswith("s3://"):
        local_rem = "/tmp/rem.tif"
        s3 = session.client("s3")
        bucket, key = rem_path[5:].split("/", 1)
        s3.download_file(bucket, key, local_rem)
        rem_path = local_rem

    if catchment_path.startswith("s3://"):
        local_catch = "/tmp/catch.tif"
        bucket, key = catchment_path[5:].split("/", 1)
        s3.download_file(bucket, key, local_catch)
        catchment_path = local_catch

    with rasterio.open(rem_path) as rem, rasterio.open(catchment_path) as catchments:
        if rem.shape != catchments.shape:
            raise ValueError("Raster dimensions mismatch")

        # Create temporary local output
        local_output = "/tmp/output.tif"
        profile = rem.profile.copy()
        profile.update(dtype="uint8", count=1, compress="lzw", nodata=255)

        with rasterio.open(local_output, "w", **profile) as dst:
            # Process data in windows
            for j in range(0, rem.height, window_size):
                for i in range(0, rem.width, window_size):
                    # Adjust window size for edge cases
                    effective_width = min(window_size, rem.width - i)
                    effective_height = min(window_size, rem.height - j)
                    window = Window(i, j, effective_width, effective_height)

                    rem_data = rem.read(1, window=window)
                    catch_data = catchments.read(1, window=window).astype(str)

                    valid_mask = rem_data >= 0
                    stages = np.vectorize(lambda x: interpolated.get(x, -9999))(
                        catch_data
                    )
                    window_result = np.where(
                        valid_mask & (stages > rem_data), 1, 0
                    ).astype(np.uint8)

                    dst.write(window_result, window=window, indexes=1)

        # Upload result to S3
        if output_path.startswith("s3://"):
            bucket, key = output_path[5:].split("/", 1)
            s3.upload_file(local_output, bucket, key)


def main():
    parser = argparse.ArgumentParser(description="Process inundation data")
    parser.add_argument(
        "--catchment-data", required=True, help="S3 path to catchment data JSON"
    )
    parser.add_argument(
        "--forecast-path", required=True, help="Path to forecast CSV file or S3 URI"
    )
    parser.add_argument(
        "--output-path", required=True, help="Output path for resulting raster (S3 URI)"
    )
    parser.add_argument(
        "--window-size", type=int, default=1024, help="Processing window size"
    )

    args = parser.parse_args()

    # Configure AWS session
    session = boto3.Session()

    # Read the catchment data from S3
    with open(args.catchment_data, "r", transport_params={"session": session}) as f:
        catchment_data = json.load(f)

    # Process inundation
    simple_inundate_catchment_data(
        catchment_data=catchment_data,
        forecast_path=args.forecast_path,
        output_path=args.output_path,
        window_size=args.window_size,
    )


if __name__ == "__main__":
    main()
