# Flood Evuation Job Arguments, Inputs, and Outputs

This repository contains a set of yaml files that specifies interfaces for the jobs that make up the FIM evaluation pipeline. The pipeline has been designed as a series of chained jobs that will be run by a batch processing solution. The primary focus is on inputs and outputs of each job and each jobs arguments/parameters. 

Below we give a human readable description of the contents of each yaml file.

## Coordinator (`coordinator`)  
### Description  
The coordinator is the entrypoint to the evaluation pipeline. It takes a gpkg containing either a polygon or multipolygon geometry and then uses that to run and monitor batch jobs for each step along the evaluation pipeline for all the polygons submitted by the user. 

The current evaluation pipeline is primarily designed to generate HAND FIM extents or depths and then evaluate these against relevant benchmark sources.

### Arguments
- **HAND Version** 
  - The HAND version argument allows the user to specify a specific version of HAND to generate extents for. This argement is required.
- **Benchmark Source** 
  - This is a string that select which source will be used to evaluate HAND against. For example 'mip-ripple' will be used to select FEMA MIP data produced by ripple. This argument is required.
- **Date Range** 
  - Certain Benchmark sources contain flood scenarios that have a time component to them. For example high water mark data is associated with the flood  event associated with a given survey. This argument allows for filtering a Benchmark source to only return benchmark data within a certain date range.
 
### Inputs
- **AOI**
  - This input is a geopackage that must contain either a polygon or multipolygon geometry. For every polygon the coordinator will generate a HAND extent and find benchmark data that lies within the polygon for the source selected by the user. The coordinator will then run all the rest of the jobs described in this repository to generate an evaluation for that polygon. 

## HAND Inundator (`hand_inundator`)
### Description  
- Generates flood extent/depth maps from a HAND REM. This job inundates a *single* hand catchment. It can be configured to return either a depth FIM or an extent FIM.

### Arguments  
- **window_size**
  - Tile processing size (256-4096px). The rasters that are used  
- **output_type**
  - Extent (binary) vs Depth (float values)  

### Input Requirements  
- **Catchment**:
  - This input is a JSON file that contains a rating curve every HydroID in a HAND catchment along with metadata necessary to process the HydroID. It has the following structure:
  ```json
  {
      "<catchment_id>": {
        "hydrotable_entries": {
          "<HydroID>": {
            "stage": [<array_of_stage_values>],
            "discharge_cms": [<array_of_discharge_values>],
            "nwm_feature_id": <integer>,
            "lake_id": <integer>
          }
          // More HydroID entries...
        },
        "raster_pair": {
          "rem_raster_path": "<path_value>",
          "catchment_raster_path": "<path_value>"
        }
      }
  }
  ```
  - The **raster_pair** lists paths to the two rasters that are used to generate the HAND extent.
  - **rem_raster_path**
    - This is a path to a HAND relative elevation tiff for this catchment. This would typically be an s3 path but could be a local filepath as well. 
  - **catchment_raster_path**
    - This is a path to a tiff that helps map every location in the catchment to a rating curve associated with that location. Every pixel is assigned an integer value that reflects the HydroID of the sub-catchment it is in. This value can then be used to look up an associated rating curve in the hydrotable_entries object inside the catchment json. This rating curve is used to interpolate a stage value for a given NWM reach discharge. If the stage value is larger than the HAND value at that pixel then the pixel is marked flooded.
- **Forecast**
  - A csv file listing NWM feature_id values and their respective discharges. A stage is obtained for these discharges for each HydroID catchment by using the rating associated with that HydroID.

### Output Specifications  
- **Inundation Raster**
  - This is a depth or extent raster generated from the HAND data. The format of this raster is specified in `hand_inundator.yml'
---

## Agreement Maker (`make-agreement`) 
### Description  
- Creates concurrence maps between 2 datasets

### Arguments  
- **Resolution**: Mandatory x/y when outputting rasters  
- **Input Compatibility**: Handles raster/vector depth/extent combos

### Input Features  
- **Dataset1/Dataset2**:  
  Raster (GEOTIFF) or Vector (GeoPackage)  
  Requires explicit geometry_type & fim_type  

### Output Options  
- **Raster**: float32(depth)/uint8(extent), auto-nodata  
- **Vector**: Point/MultiPoint/Polygon GeoPackage  

---

## Mosaic Maker (`mosaic-extents`) 
### Description  
- Harmonizes overlapping flood observations

### Processing Parameters  
- **Target Resolution**: Required for raster outputs  

### Input Flexibility  
- **Files**: Array of TIFF/GeoJSON/GeoPackage  
- **Clipping**: Optional GeoJSON boundary  

### Output Types  
- **Raster**: Uniform GRID in EPSG:5070  
- **Vector**: Unified features in GeoPackage  

---

## Metrics Calculator (`calculate-agreement-metrics`) 
### Description  
- Quantifies spatial agreement accuracy

### Input Compatibility  
- Accepts raster TIFF or polygon GeoPackage  

### Output Metrics  
- CSI/POD/FAR scores (0-1 range)  

---

