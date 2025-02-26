#!/usr/bin/env python3
import unittest
import os
import subprocess
import rasterio
import numpy as np
import sys


class TestMosaicScript(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Get the directory containing test data
        cls.test_dir = os.path.dirname(os.path.abspath(__file__))
        cls.mock_data_dir = os.path.join(cls.test_dir, "mock_data")

        # Ensure mock_data directory exists
        os.makedirs(cls.mock_data_dir, exist_ok=True)

        # Path to the script being tested
        cls.script_path = os.path.join(
            os.path.dirname(cls.test_dir), "fim_mosaicker", "mosaic.py"
        )

        # Verify script exists
        if not os.path.exists(cls.script_path):
            raise FileNotFoundError(f"Script not found at {cls.script_path}")

        # Input raster paths (with .tif extension)
        cls.raster_paths = [
            os.path.join(cls.mock_data_dir, "raster1.tif"),
            os.path.join(cls.mock_data_dir, "raster2.tif"),
            os.path.join(cls.mock_data_dir, "raster3.tif"),
            os.path.join(cls.mock_data_dir, "raster4.tif"),
        ]

        # Output path
        cls.output_path = os.path.join(cls.mock_data_dir, "mosaicked_raster.tif")

        # Check for input files (print warning rather than failing setup)
        missing_files = []
        for raster_path in cls.raster_paths:
            if not os.path.exists(raster_path):
                missing_files.append(raster_path)

        if missing_files:
            print(
                f"WARNING: The following test raster files are missing: {missing_files}"
            )
            print("Tests may fail if these files are required.")

    def test_mosaic_creation(self):
        # Skip test if any input files are missing
        for raster_path in self.raster_paths:
            if not os.path.exists(raster_path):
                self.skipTest(f"Skipping test because {raster_path} is missing")

        # Remove the output file if it exists
        if os.path.exists(self.output_path):
            os.remove(self.output_path)

        # Run the mosaic script with FIM type set to extent
        cmd = [
            sys.executable,  # Use the current Python interpreter
            self.script_path,
            *self.raster_paths,
            self.output_path,
            "--fim-type",
            "extent",
        ]

        # Print the command being run
        print(f"Running command: {' '.join(cmd)}")

        # Run with full output capture
        result = subprocess.run(cmd, capture_output=True, text=True)

        # Print full output for debugging
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")

        self.assertEqual(
            result.returncode, 0, f"Script failed with error: {result.stderr}"
        )

        # Check if the output file was created
        self.assertTrue(
            os.path.exists(self.output_path), "Mosaic output file was not created."
        )

        # Verify the output raster properties
        with rasterio.open(self.output_path) as src:
            # Check data type (uint8 for extent)
            self.assertEqual(
                src.dtypes[0],
                "uint8",
                f"Expected uint8 data type for extent, got {src.dtypes[0]}",
            )

            # Check nodata value (255 for extent)
            self.assertEqual(
                src.nodata,
                255,
                f"Expected 255 nodata value for extent, got {src.nodata}",
            )

            # Check that data exists
            data = src.read(1)
            self.assertTrue(
                (data != src.nodata).any(),
                "Raster contains no valid data (all nodata values)",
            )

            # For extent type, check that all values are either 0, 1 or nodata
            valid_data = data[data != src.nodata]
            if len(valid_data) > 0:
                self.assertTrue(
                    np.all((valid_data == 0) | (valid_data == 1)),
                    "Extent raster contains values other than 0, 1, and nodata",
                )

    @classmethod
    def tearDownClass(cls):
        print("Cleaning up...")
        # Uncomment to clean up the output file after test
        # if os.path.exists(cls.output_path):
        #     os.remove(cls.output_path)


if __name__ == "__main__":
    unittest.main()
