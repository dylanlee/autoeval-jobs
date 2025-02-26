#!/usr/bin/env python3
import os
import json
import argparse
from smart_open import open
import numpy as np
import pandas as pd
import rasterio
from rasterio.windows import Window
import boto3
from typing import Optional, Union, Dict, Any


def inundate(
    catchment_ Union[str, Dict[str, Any]],
    forecast_path: str,
    output_path: str,
    window_size: int = 1024,
) -> str:
    """
    Generate inundation map from NWM forecasts and HAND data.

    Parameters
    ----------
    catchment_data : str or dict
        Path to catchment JSON file or the loaded catchment data dictionary.
    forecast_path : str
        Path to forecast CSV file.
    output_path : str
        Output path for inundation raster.
    window_size : int, optional
        Processing window size in pixels, by default 1024.

    Returns
    -------
    str
        Path to the output inundation raster.

    Raises
    ------
    ValueError
        If no matching forecast data for catchment features.
    """
    # Configure AWS credentials for raster access
    session = boto3.Session(region_name=os.environ.get('AWS_DEFAULT_REGION', 'us-east-1'))
    creds = session.get_credentials()
    if creds:
        os.environ.update(
            {
                "AWS_ACCESS_KEY_ID": creds.access_key,
                "AWS_SECRET_ACCESS_KEY": creds.secret_key,
                **({"AWS_SESSION_TOKEN": creds.token} if creds.token else {}),
            }
        )

    # Load data
    if isinstance(catchment_data, str):
        with open(catchment_data) as f:
            catchment = json.load(f)
    else:
        catchment = catchment_data

    with open(forecast_path, "r") as f:
        forecast = pd.read_csv(
            f,
            header=0,
            names=["feature_id", "discharge"],
            dtype={"feature_id": int, "discharge": float},
        )

    # Create stage mapping with proper group handling
    hydro_df = pd.DataFrame(catchment["hydrotable_entries"]).T.reset_index(
        names="HydroID"
    )
    hydro_df = hydro_df[hydro_df.lake_id == -999].explode(["stage", "discharge_cms"])
    hydro_df = hydro_df.astype(
        {
            "HydroID": "int32",
            "stage": "float32",
            "discharge_cms": "float32",
            "nwm_feature_id": "int32",
        }
    )

    # Create merged DataFrame
    merged = hydro_df.merge(
        forecast, left_on="nwm_feature_id", right_on="feature_id", how="inner"
    )

    merged.set_index("HydroID", inplace=True)

    stage_map = (
        merged.groupby(level=0, group_keys=False)
        .apply(lambda g: np.interp(g.discharge.iloc[0], g.discharge_cms, g.stage))
        .to_dict()
    )

    if merged.empty:
        raise ValueError("No matching forecast data for catchment features")

    # Create temporary output path
    temp_output = "/tmp/temp_inundation.tif"

    # Windowed raster processing
    with rasterio.open(
        catchment["raster_pair"]["rem_raster_path"]
    ) as rem, rasterio.open(catchment["raster_pair"]["catchment_raster_path"]) as cat:

        profile = rem.profile
        profile.update(dtype="uint8", count=1, nodata=255, compress="lzw")

        with rasterio.open(temp_output, "w", **profile) as dst:
            for y in range(0, rem.height, window_size):
                h = min(window_size, rem.height - y)
                for x in range(0, rem.width, window_size):
                    w = min(window_size, rem.width - x)
                    window = Window(x, y, w, h)

                    rem_win = rem.read(1, window=window)
                    cat_win = cat.read(1, window=window).astype("int32")

                    valid_mask = rem_win >= 0
                    stages = np.vectorize(lambda x: stage_map.get(x, -9999))(cat_win)
                    inundation = (
                        (stages > rem_win) & valid_mask & (stages != -9999)
                    ).astype("uint8")

                    dst.write(inundation, 1, window=window)

    # Handle output path
    if output_path.startswith("s3://"):
        s3_path = output_path[5:]
        bucket, _, key = s3_path.partition("/")
        boto3.client("s3").upload_file(temp_output, bucket, key)
    else:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        os.replace(temp_output, output_path)

    return output_path


def main():
    """Parse command line arguments and run the inundation process."""
    parser = argparse.ArgumentParser(
        description="Inundation mapping from NWM forecasts",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--catchment-data", required=True, help="Path to catchment JSON"
    )
    parser.add_argument(
        "--forecast-path", required=True, help="Path to forecast CSV"
    )
    parser.add_argument(
        "--output-path", required=True, help="Output path for inundation raster"
    )
    parser.add_argument(
        "--window-size", type=int, default=1024, help="Processing window size in pixels"
    )
    args = parser.parse_args()

    try:
        output_raster = inundate(
            catchment_data=args.catchment_data,
            forecast_path=args.forecast_path,
            output_path=args.output_path,
            window_size=args.window_size,
        )
        print(f"Successfully created inundation raster: {output_raster}")
    except Exception as e:
        import sys
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
