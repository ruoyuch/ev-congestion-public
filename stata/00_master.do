**************************************************
* The electric vehicle transition exacerbates traffic congestion in California
* Ruoyu Chen, Hang Liu, Mingzhi Zhou
*
* Master do-file: runs every Stata step in order. Run from the stata/ folder:
*     cd stata
*     stata-mp -b do 00_master.do
* or let ../pipeline/run_all.py call it (its "stata" stage). Paths are read from ../.env (see _setup.do).
*
* Requires Stata 17+ and reghdfe, ftools, ivreghdfe, ivreg2, ranktest, estout
* (install once with: do install_packages.do).
*
* Inputs ($INTERMEDIATE, written by the Python pipeline):
*   vehicle_proportion.csv, zip_code_congestion_index.csv,
*   zip_code_congestion_index_radius.csv, zip_code_evcs_count.csv,
*   zip_code_acs.csv, zip_code_acs_income_bins.csv,
*   uz_ntd_ev.csv, zip_neighbor_pairs.csv
* plus $INPUT/zip_county_crosswalk.xlsx and zip_county_sub_crosswalk.xlsx
*
* Each step can also be run on its own once 01_build_data.do has been run.
* Runtime: a few minutes; step 09 (1,000-draw permutation test) is the slowest.
**************************************************
do "_setup.do"

local steps 01_build_data 02_main_tables 03_spatial_scale 04_heterogeneity ///
            05_lagged 06_iv 07_covid 08_rings 09_randomization 10_fe_robustness

* run a subset with:  do 00_master.do 02_main_tables 10_fe_robustness
if `"`0'"' != "" local steps `0'

foreach s of local steps {
    display as result _n "=== `s' ===" _n
    do "`s'.do"
}
display as result _n "All steps finished. Outputs in $OUTPUT"
