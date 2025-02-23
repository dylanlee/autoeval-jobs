#!/usr/bin/env python3
import unittest
import os
import subprocess
import rasterio


class TestMosaicScript(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Get the directory containing test data
        cls.test_dir = os.path.dirname(os.path.abspath(__file__))
        cls.mock_data_dir = os.path.join(cls.test_dir, "mock_data")

        # Path to the script being tested
        cls.script_path = os.path.join(
            os.path.dirname(cls.test_dir), "fim_mosaicker", "mosaic.py"
        )

        # Input raster paths
        cls.raster_paths = [
            os.path.join(cls.mock_data_dir, "raster1.tif"),
            os.path.join(cls.mock_data_dir, "raster2.tif"),
            os.path.join(cls.mock_data_dir, "raster3.tif"),
            os.path.join(cls.mock_data_dir, "raster4.tif"),
        ]

        # Output path
        cls.output_path = os.path.join(cls.mock_data_dir, "mosaicked_raster.tif")

    def test_mosaic_creation(self):
        # Remove the output file if it exists
        if os.path.exists(self.output_path):
            os.remove(self.output_path)

        # Run the mosaic script
        cmd = [
            "python3",
            self.script_path,
            *self.raster_paths,
            str(self.output_path),
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(
            result.returncode, 0, f"Script failed with error: {result.stderr}"
        )

        # Check if the output file was created
        self.assertTrue(
            os.path.exists(self.output_path),
            "Mosaic output file was not created.",
        )

        # Optionally, add more checks to verify the output raster

    @classmethod
    def tearDownClass(cls):
        # Clean up the output file
        if os.path.exists(cls.output_path):
            os.remove(cls.output_path)


if __name__ == "__main__":
    unittest.main()
