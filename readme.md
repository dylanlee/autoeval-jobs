# tests
To test the inundate script run:

```
python3 -m unittest test_inundate.py
```

# Interface definitions for FIM Evaluation Jobs Arguments, Inputs, and Outputs

This interface directory contains a set of yaml files that specifies interfaces for the jobs that make up the HAND FIM evaluation pipeline. The pipeline has been designed as a series of chained jobs that will be run by a batch processing solution. The primary focus of this repo is on describing inputs and outputs of each job and each jobs arguments/parameters. 

Below we give a human readable description of the contents of each yaml file. The descriptions also expand on the anticipated behavior of the jobs for common input and argument combinations. 

## Coordinator (`coordinator`)  
### Description  
The coordinator is the entry point to the evaluation pipeline. It takes a gpkg containing either a polygon or multipolygon geometry and then uses that to run and monitor batch jobs for each step along the evaluation pipeline for all the polygons submitted by the user. 

The current evaluation pipeline is primarily designed to generate HAND FIM extents or depths and then evaluate these against relevant benchmark sources.

### Arguments
- **HAND Version** 
  - The HAND version argument allows the user to specify a specific version of HAND to generate extents for. This argument is required.
- **Benchmark Source** 
  - This is a string that select which source will be used to evaluate HAND against. For example 'ripple-mip' will be used to select FEMA MIP data produced by ripple. This argument is required.
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
  - Tile processing size (256-4096px). Rasters are processed by tile to limit memory usage. 
- **output_type**
  - Extent (binary) vs Depth (float values)  

### Inputs 
- **catchment**:
  - This input is a JSON file that contains a rating curve every HydroID in a given HAND catchment along with metadata necessary to process the HydroID. It has the following structure:
  ```json
  {
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
  ```
  - The **raster_pair** lists paths to the two rasters that are used to generate the HAND extent.
    - **rem_raster_path**
    - This is a path to a HAND relative elevation tiff for this catchment. This would typically be an s3 path but could be a local filepath as well. 
    - **catchment_raster_path**
    - This is a path to a tiff that helps map every location in the catchment to a rating curve associated with that location. Every pixel is assigned an integer value that reflects the HydroID of the sub-catchment it is in. This value can then be used to look up an associated rating curve in the hydrotable_entries object inside the catchment json. This rating curve is used to interpolate a stage value for a given NWM reach discharge. If the stage value is larger than the HAND value at that pixel then the pixel is marked flooded.
- **flow_scenario**
  - A csv file listing NWM feature_id values and their respective discharges. A stage is obtained for these discharges for each HydroID catchment by using the rating associated with that HydroID.

### Outputs 
- **Inundation Raster**
  - This is a depth or extent raster generated from the HAND data. The format of this raster is specified in `hand_inundator.yml'
---

## Mosaic Maker (`fim_mosaicker`) 
### Description  
This job mosaics flood extents and benchmark raster data from either HAND or benchmark sources using a pixel-wise NAN-MAX selection policy. That is, for all the images being mosaicked if there are overlapping raster pixels then the maximum value of the overlapping rasters at that pixel location is selected. No-Data values are not considered when selecting the maximum (they are treated as Nan) unless all the pixels are No-Data. Rasters can be either depth or extent rasters and the mosaicking policy for overlapping rasters will remain the same. Common input combinations and the behavior of the jobs in those cases are described below.

If vector data is being mosaicked then the behavior will depend on what type of geometry is described by the vector data. The allowed geometries are polygon, multipolygon, point, or multipoint.  

In the case of a polygon or multipolygon geometries they will be treated as only describing an extent. Any point geometries mosaicked with them will be cast to extents. Rasters mosaicked with these geometries will be cast to polygonal extents as well and the final output will a mosaicked polygon, multipolygon, or polygon with adjacent points.

In the case of point or multipoint geometries they can contain either extents or depths in their attributes and will pass through the type of information they are tagged with unless they are being mosaicked with polygon geometries. When a raster is being mosaicked with point geometries, locations where the raster coincide with the point values will be converted to a point geometry by averaging extent or depth pixel values within a buffer of the point location. This value will then be mosaicked with the value described by the overlapping point geometries depth or extent attribute. The raster values that don't coincide with points in the point geometry will be discarded. Additional attributes from the original point geometries will be passed through and returned with the mosaicked geometries.

### Arguments
- **Target Resolution**
  - Required for raster outputs  

### Inputs
- **Files**: 
  - Array of paths to TIFF/GeoJSON/GeoPackage rasters and/or vector files. If a vector is listed in the array then the output will be a vector. 
- **Clipping**
  - Optional GeoJSON boundary to clip the mosaicked output to. This input will always be given in the HAND FIM evaluation pipeline and will describe the ROI being evaluated.

### Outputs 
- **Raster**
  - In the case of raster output, the output will be a single mosaicked raster.
- **Vector** 
  - In the case of vector output, the output will be a single mosaicked vector tiff file.

---

## Agreement Maker (`agreement_maker`) 
### Description  
Creates an agreement map showing where a pair of input data (raster or vector) spatially concur. The job is designed to work with any combination of raster or vector input pairs. The job also works with depth or extent data with the assumption that a given pair will be either both depths or extents. Produces either a continuous  agreement map when the inputs are depths or a categorical agreement map for extents. The output is raster or vector data in EPSG:5070.

Similarly to the mosaicking job geometry inputs and outputs, polygon geometries can only describe extents.

### Arguments  
- **Resolution**
  - Mandatory x/y pixel resolution that is used when outputting rasters  

### Inputs
- **Dataset1/Dataset2**:  
  - Raster or Vector (as geopackage). If a vector must be either a point, multipoint, multipolygon, or polygon geometry.  

- **Mask dictionary**
  - This is an optional json object that is composed of sub-objects that include paths to geopackage of masks to exclude or include in the final produced agreement. The input format is identical to the previous format that was previously used to mask areas over which to evaluate FIM model skill. Each mask geometry can also be buffered by setting a buffer flag to an integer value (with units of meters) in the sub-dictionaries "buffer" key.

  ```json
  mask_dict = {
      "levees": {
          "path": levee_path,
          "buffer": None,
          "operation": "exclude",
      },
      "waterbodies": {
          "path": water_bod_path,
          "buffer": None,
          "operation": "exclude",
      },
  }
  ```
  
### Outputs 
Output is either a single raster or a geopackage of vector information.

- **Raster**
  - See `agreement_maker.yml` for a description of the output raster format.
- **Vector**: 
  - See `agreement_maker.yml` for a description of output vector format. The returned geopackage could have additional attributes that are passed through from the input vector data to the output data. 

---

## Metrics Calculator (`metrics_calculator`) 
### Description  
This job is designed to take an agreement map and calculate summary metrics of the agreement of two FIMs over a given ROI.

### Input  
- **Agreement map**
  - Accepts raster TIFF or geopackage containing point or polygon geometries. The type of agreement map will be surmised by the number and type of data values in the raster or the geometry's attributes. 

### Output  
- **Metrics json**
  - The output will be a json file containing the metrics the user requested. `metrics_calculator.yml` lists a small subset of possible metrics.
---

