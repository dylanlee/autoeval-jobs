import numpy as np
import pandas as pd
import rasterio
from rasterio import DatasetReader


def inundate(catchment_data: dict, forecast: str | pd.DataFrame) -> np.ndarray:
    """Calculate inundation using JSON-structured data with lake filtering and feature_id mapping."""
    # Open raster datasets
    rem_path = catchment_data["raster_pairs"]["rem_raster_path"]
    catchment_path = catchment_data["raster_pairs"]["catchment_raster_path"]

    with rasterio.open(rem_path) as rem, rasterio.open(catchment_path) as catchments:
        rem_array = rem.read(1)
        catchments_array = catchments.read(1)

    # Build hydro_table with lake filtering
    hydro_entries = catchment_data["hydrotable_entries"]

    # Create DataFrame with vectorized operations for efficiency
    rows = []
    for hydro_id, curve in hydro_entries.items():
        # Filter lakes at source to avoid storing unnecessary data
        if curve.get("lake_id", -999) != -999:
            continue

        n = len(curve["stage"])
        rows.append(
            {
                "HydroID": hydro_id,
                "feature_id": curve["nwm_feature_id"],
                "stage": curve["stage"],
                "discharge_cms": curve["discharge_cms"],
                "_curve_length": n,  # Track for quality control
            }
        )

    if not rows:
        raise ValueError("No valid hydrotable entries found (after lake filtering)")

    hydro_table = pd.DataFrame(rows).explode(["stage", "discharge_cms"])
    hydro_table[["stage", "discharge_cms"]] = hydro_table[
        ["stage", "discharge_cms"]
    ].astype(float)

    # Load and validate forecast data
    if isinstance(forecast, str):
        forecast = pd.read_csv(forecast, dtype={"feature_id": int, "discharge": float})

    # Ensure matching feature_id types
    hydro_table["feature_id"] = hydro_table["feature_id"].astype(int)
    forecast["feature_id"] = forecast["feature_id"].astype(int)

    # Merge forecast with rating curves
    merged = hydro_table.merge(forecast, on="feature_id", how="inner").dropna(
        subset=["stage", "discharge_cms", "discharge"]
    )

    # Group-level interpolation with pandas methods
    def interpolate_group(group):
        # Sort by discharge_cms for reliable interpolation
        sorted_group = group.sort_values("discharge_cms")
        try:
            return pd.Series(
                {
                    "HydroID": group.name,
                    "stage": np.interp(
                        group["discharge"].iloc[0],
                        sorted_group["discharge_cms"],
                        sorted_group["stage"],
                    ),
                }
            )
        except ValueError as e:
            raise ValueError(f"Interpolation failed for HydroID {group.name}") from e

    stages_df = merged.groupby("HydroID", group_keys=False).apply(interpolate_group)

    # Create HydroID to stage mapping
    stages_dict = stages_df.set_index("HydroID")["stage"].astype(float)
    stages_dict.index = stages_dict.index.astype(str)  # Match raster dtype

    # Raster processing with numpy for performance
    hydro_ids = catchments_array.ravel().astype(str)
    valid_mask = (rem_array.ravel() >= 0) & (hydro_ids != "0")  # Assuming 0 is no-data

    # Vectorized lookup using pandas categoricals for memory efficiency
    hydro_ids_series = pd.Series(hydro_ids, dtype="category")
    stage_array = hydro_ids_series.map(stages_dict).values.astype(float)

    # Calculate inundation
    rem_flat = rem_array.ravel()
    inundation = np.zeros_like(rem_array, dtype=np.uint8)

    # Use numpy boolean indexing for final calculation
    valid_idx = valid_mask & ~np.isnan(stage_array)
    inundation.flat[valid_idx] = (stage_array[valid_idx] > rem_flat[valid_idx]).astype(
        np.uint8
    )

    return inundation
