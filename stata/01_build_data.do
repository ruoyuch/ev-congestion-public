**************************************************
* 01_build_data.do -- Merge the ZIP-year CSVs into the analysis datasets (.dta).
* Outputs: maindata.dta, maindata_with_radius.dta, maindata_r5_iv.dta, uantddata.dta
* Run via 00_master.do (or run_all.py); standalone runs load _setup.do.
**************************************************
if "$EVC_SETUP" == "" do "_setup.do"

**************************************************
* 1. Clean, link, and save the data
**************************************************
* 1.1. Prepare zip code level data for the main analysis
**************************************************
* Import the datasets and save them as temporary files
import delimited "$INTERMEDIATE/vehicle_proportion.csv", clear
tempfile vehicle_data
save `vehicle_data'

import delimited "$INTERMEDIATE/zip_code_congestion_index.csv", clear
tempfile congestion_data
save `congestion_data'

import delimited "$INTERMEDIATE/zip_code_evcs_count.csv", clear
tempfile evcs_data
rename zip zip_code
save `evcs_data'

import delimited "$INTERMEDIATE/zip_code_acs.csv", clear
tempfile acs_data
rename geo_code zip_code
save `acs_data'

import excel "$INPUT/zip_county_crosswalk.xlsx", clear firstrow
tempfile crosswalk_data1
rename ZIP zip_code
rename COUNTY county_code
keep if USPS_ZIP_PREF_STATE == "CA"
keep zip_code county_code
destring zip_code, replace
duplicates report zip_code
duplicates drop zip_code, force //Check for duplicates in zip_code
save `crosswalk_data1'

import excel "$INPUT/zip_county_sub_crosswalk.xlsx", clear firstrow
tempfile crosswalk_data2
rename ZIP zip_code
rename COUNTY_SUB county_sub_code
keep if USPS_ZIP_PREF_STATE == "CA"
keep zip_code county_sub_code
destring zip_code, replace
duplicates report zip_code
duplicates drop zip_code, force //Check for duplicates in zip_code
save `crosswalk_data2'

* Merge the datasets by zip code and year
use `vehicle_data', clear //start with this because we cannot continue with samples without X
merge 1:1 zip_code year using `congestion_data'
drop _merge
merge m:1 zip_code using `crosswalk_data1'
drop _merge
merge m:1 zip_code using `crosswalk_data2'
drop _merge
merge 1:1 zip_code year using `acs_data'
drop _merge
merge 1:1 zip_code year using `evcs_data'
drop _merge


* Drop if count_batteryelectricbev is missing
drop if count_batteryelectricbev == .

* Save the final dataset
save "$INTERMEDIATE/maindata.dta", replace

**************************************************
* 1.2. Add radius data to the main dataset
**************************************************
* Import radius-wide dataset
import delimited "$INTERMEDIATE/zip_code_congestion_index_radius.csv", clear
describe

* Ensure zip_code and year are correct format
destring zip_code, replace force
destring year, replace force

tempfile radius_wide
save `radius_wide'

use "$INTERMEDIATE/maindata.dta", clear
destring zip_code, replace force
destring year, replace force

merge 1:1 zip_code year using `radius_wide'

* Check merge status
tab _merge
drop if _merge == 2    // radius data but no main record
drop _merge

save "$INTERMEDIATE/maindata_with_radius.dta", replace

**************************************************
* 1.3. Build r=5km + IV dataset for Table 1
**************************************************
import delimited "$INTERMEDIATE/zip_code_acs_income_bins.csv", clear
rename geo_code zip_code
destring zip_code, replace force
keep zip_code year hh_total ///
    hh_inc_100_125k hh_inc_125_150k hh_inc_150_200k hh_inc_gt200k
tempfile income_bins
save `income_bins'

use "$INTERMEDIATE/maindata_with_radius.dta", clear
destring zip_code year, replace force
xtset zip_code year
merge 1:1 zip_code year using `income_bins'
drop if _merge == 2
drop _merge

* z_cap_100: pre-policy HH share with income >= $100K x post-2016
*   Avg CA HH size ~2.86 (≈3-person), CVRP HH-adjusted benchmark ~$99K
gen share_above_100k = (hh_inc_100_125k + hh_inc_125_150k + ///
                         hh_inc_150_200k + hh_inc_gt200k) / hh_total
gen post_cvrp = (year >= 2017)
gen pre_raw_100k = share_above_100k if inrange(year, 2014, 2015)
bysort zip_code: egen pre_cvrp_above_100k = mean(pre_raw_100k)
drop pre_raw_100k
gen z_cap_100 = pre_cvrp_above_100k * post_cvrp

encode county_code, gen(county_code_fe)
gen str15 county_year_str = string(county_code_fe) + "_" + string(year)
encode county_year_str, gen(county_year_fe)

save "$INTERMEDIATE/maindata_r5_iv.dta", replace

**************************************************
* 1.4. Prepare urbanized area (ua) level data for the PT analysis
**************************************************
* Import the datasets and save them as temporary files
import delimited "$INTERMEDIATE/uz_ntd_ev.csv", clear

* Generate variables for analysis
prep_vars
label variable log_count_bev "Log BEV count"
gen log_pt_ridership  = log(pt_ridership)
label variable log_pt_ridership "Log public transit ridership"

* Save the dataset
save "$INTERMEDIATE/uantddata.dta", replace
