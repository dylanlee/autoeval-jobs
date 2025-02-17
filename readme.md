# Flood Analysis Toolkit Interface Documentation

## HAND Inundator (`hand_inundator`)
### Description  
- Generates flood extent/depth maps using HAND methodology

### Key Arguments  
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

### Configuration  
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

## Coordinator (`coordinator`)  
### Description  
- Orchestrates batch validation workflows  

### Configuration Hooks  
- **HAND Version** identifier  
- **Benchmark Source** metadata  
- Optional temporal **Date Range** filter  

### Spatial Constraints  
- **AOI**: GeoPackage polygon/multipolygon  
