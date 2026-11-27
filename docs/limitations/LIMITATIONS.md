# Limitations

**Scope.** Research prototype for Nigeria only. It is not for military, tactical routing, autonomous
driving or safety certification.

**No live data.** Every layer is historical: the Hadejia flood events (2020, 2022), EO4Forest land cover
(Dec 2023), Soils4Africa field visits (2022–23) and the wetland study (map year 2018). No layer
describes conditions today.

**Narrow coverage.** Wall-to-wall local layers exist for only two areas:
- Lagos/Ogun: EO4Forest, 20 m.
- Hadejia LGA (~48 km²): flood, water and land cover, 3 m.

Everywhere else in Nigeria, the app has only:
- the drainage basin;
- a Soils4Africa field site, if one lies within 1 km.

**No soil composition.** No measured, georeferenced sand/silt/clay data for Nigeria is available to this
project (see the gap report). The app returns *unavailable*; it never estimates. Modelled products
(SoilGrids, iSDAsoil) are not ingested yet. When they are, they will be labelled as modelled, at native
resolution, with intervals.

**Map classes are not texture.** The "Soil" (EO4Forest) and "Bare soil" (Hadejia) classes mean exposed
ground surface. They do not mean sand.

**Published accuracies are optimistic.** EO4Forest validation points are close to training points
(median 212 m), so the reported scores are not independent. Hadejia flood test points are labelled from
Sentinel-2 MNDWI maps: that is sensor-independent, but not field truth.

**Flood maps.** A pixel marked 0 means "not mapped as flooded or no data". The source does not
distinguish the two. The maps carry no depth, velocity or duration-of-ponding information.

**Equipment screening is qualitative.** There are no outcome data linking soil or water conditions to
vehicle performance in Nigeria. The screening therefore only reports observed indicators and evidence
gaps, and it always recommends qualified inspection. The supervised trafficability module is disabled.

**Photos are not analysed.** No image model has been validated on Nigerian labelled imagery.

**Boundary.** geoBoundaries gbOpen (GRID3, year represented 2022). Points within metres of the
national border may be misclassified at the boundary's precision.

**Soils4Africa caveats.** The plots are agricultural monitoring sites, not representative of roads or
construction sites. The publisher states that QC is ongoing.
