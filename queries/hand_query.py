from sqlalchemy import create_engine, text
from typing import Optional, Dict, Any
import json


class HANDQueryWrapper:
    def __init__(self, connection_string: str):
        """
        Initialize the query wrapper with a database connection string.

        Args:
            connection_string (str): SQLAlchemy connection string
                e.g., "postgresql://user:password@localhost:5432/dbname"
        """
        self.engine = create_engine(connection_string)

    def get_roi_catchments(
        self, polygon_wkt: str, srid: int, hand_version: str
    ) -> Dict[str, Any]:
        """
        Query catchment data based on an intersecting polygon.

        Args:
            polygon_wkt (str): WKT representation of the polygon
            srid (int): Spatial Reference System Identifier for the input polygon
            hand_version (str): Version identifier for HAND data

        Returns:
            Dict[str, Any]: JSON response containing catchment data
        """
        query = """
                WITH intersecting_catchments AS (
                    SELECT DISTINCT c.catchment_id
                    FROM Catchments c
                    WHERE ST_Intersects(
                        c.geometry, 
                        ST_Transform(
                            ST_SetSRID(ST_GeomFromText(:polygon), :srid),
                            ST_SRID(c.geometry)
                        )
                    )
                ),
                hydrotable_arrays AS (
                    SELECT 
                        h.catchment_id,
                        h.HydroID,
                        jsonb_build_object(
                            'stage', array_agg(stage ORDER BY stage),
                            'discharge_cms', array_agg(discharge_cms ORDER BY stage),
                            'nwm_feature_id', MIN(nwm_feature_id)::integer,
                            'lake_id', MIN(lake_id)::integer
                        ) as hydro_data
                    FROM Hydrotables h
                    JOIN intersecting_catchments ic ON h.catchment_id = ic.catchment_id
                    WHERE h.hand_version_id = :hand_version
                    GROUP BY h.catchment_id, h.HydroID
                ),
                raster_pairs AS (
                    SELECT DISTINCT ON (r.catchment_id)
                        r.catchment_id,
                        jsonb_build_object(
                            'rem_raster_path', r.raster_path,
                            'catchment_raster_path', cr.raster_path
                        ) as raster_pair
                    FROM HAND_REM_Rasters r
                    LEFT JOIN HAND_Catchment_Rasters cr ON r.rem_raster_id = cr.rem_raster_id
                    JOIN intersecting_catchments ic ON r.catchment_id = ic.catchment_id
                    WHERE r.hand_version_id = :hand_version
                    ORDER BY r.catchment_id, r.rem_raster_id
                )
                SELECT jsonb_pretty(
                    jsonb_build_object(
                        'hand_version', :hand_version,
                        'catchments', COALESCE(jsonb_object_agg(
                            c.catchment_id,
                            jsonb_build_object(
                                'hydrotable_entries', COALESCE((
                                    SELECT jsonb_object_agg(HydroID, hydro_data)
                                    FROM hydrotable_arrays h
                                    WHERE h.catchment_id = c.catchment_id
                                ), '{}'::jsonb),
                                'raster_pair', COALESCE((
                                    SELECT raster_pair
                                    FROM raster_pairs rp
                                    WHERE rp.catchment_id = c.catchment_id
                                ), '{}'::jsonb)
                            )
                        ), '{}'::jsonb)
                    )
                ) AS result
                FROM intersecting_catchments ic
                JOIN Catchments c ON c.catchment_id = ic.catchment_id;
        """

        try:
            with self.engine.connect() as connection:
                result = connection.execute(
                    text(query),
                    {
                        "polygon": polygon_wkt,
                        "srid": srid,
                        "hand_version": hand_version,
                    },
                ).scalar()

                # Parse the JSON string result
                if result:
                    return json.loads(result)
                return {}

        except Exception as e:
            raise Exception(f"Error executing query: {str(e)}")

    def close(self):
        """Close the database connection."""
        self.engine.dispose()


# Example usage:
if __name__ == "__main__":
    # Connection string example
    conn_str = "postgresql://user:password@localhost:5432/hydro_db"

    # Example polygon (WKT format)
    example_polygon = "POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))"

    # Create query wrapper instance
    query_wrapper = HANDQueryWrapper(conn_str)

    try:
        # Execute query
        result = query_wrapper.get_roi_catchments(
            polygon_wkt=example_polygon, srid=4326, hand_version="v1.0"  # WGS84
        )

        # Print results
        print(json.dumps(result, indent=2))

    finally:
        # Clean up
        query_wrapper.close()
