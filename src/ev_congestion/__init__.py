"""Electric vehicle adoption and freeway congestion in California.

Python half of the replication pipeline. Each module turns one source into
a tidy ZIP-year (or UZA-year) table that the Stata do-files in ``stata/``
merge and analyze. ``pipeline/run_all.py`` runs everything in
order; see the README for the data flow.

Modules
-------
config         paths and parameters from ``.env``
pems_download  raw PeMS files (Selenium; needs a PeMS account)
station_year   raw station-hour files -> station-year speed and flow
zip_traffic    station-year -> ZIP-year traffic (within ZIP and 1-15 km radii)
vehicles       DMV/CEC registrations -> ZIP-year fleet counts and shares
covariates     ACS controls, income bins, chargers
transit        ZIP panel -> urbanized-area panel with NTD ridership
neighbors      ZIP neighbor pairs for the ring specifications
maps           Figure 1 maps
"""

import os as _os
import sys as _sys

# Point PROJ/GDAL at this interpreter's own data files. A stale PROJ_DATA from
# another conda env in the shell otherwise breaks CRS transformations.
_prefix = _os.path.dirname(_os.path.dirname(_sys.executable))
if _os.path.isdir(_os.path.join(_prefix, "share", "proj")):
    _os.environ["PROJ_DATA"] = _os.path.join(_prefix, "share", "proj")
    _os.environ.pop("PROJ_LIB", None)
if _os.path.isdir(_os.path.join(_prefix, "share", "gdal")):
    _os.environ["GDAL_DATA"] = _os.path.join(_prefix, "share", "gdal")

__version__ = "0.1.0"
