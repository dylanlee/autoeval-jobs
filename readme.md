# Flood Evuation Job Arguments, Inputs, and Outputs

This repository contains a set of yaml files that specifies interfaces for the jobs that make up the FIM evaluation pipeline. The pipeline has been designed as a series of chained jobs that will be run by a batch processing solution. The primary focus is on inputs and outputs of each job and the job arguments/parameters. 

Below we give a human readable description of the contents of each yaml file.

## Coordinator (`coordinator`)  
### Description  
The coordinator is the entrypoint to the evaluation pipeline. It takes a gpkg containing either a polygon or multipolygon geometry and then uses that to run and monitor batch jobs for each step along the evaluation pipeline for all the polygons submitted by the user. 

The current evaluation pipeline is primarily designed to generate HAND FIM extents or depths and then evaluate these against relevant benchmark sources.

### Arguments
- **HAND Version** identifier  
  - The HAND version argument allows the user to specify a specific version of HAND to generate extents for. This argement is required.
- **Benchmark Source** metadata  
- Optional temporal **Date Range** filter  


 
### Inputs
- **AOI**: GeoPackage polygon/multipolygon  

## HAND Inundator (`hand_inundator`)
### Description  
- Generates flood extent/depth maps using HAND methodology

### Arguments  
- `window_size`: Tile processing size (256-4096px)  
- `output_type`: Extent (binary) vs Depth (float values)  

### Input Requirements  
- **Catchment**: JSON with hydro-id metadata  
- **Forecast**: NWM discharge CSV  
- **REMraster**: HAND relative elevation TIFF  
- **Catchmentraster**: Spatial ID mapping TIFF  

### Output Specifications  
- **Inundation Raster**:  
  *Extent*: uint8, nodata=255 | *Depth*: float32, nodata=-9999  
  CRS: EPSG:5070, LZW compression  

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

