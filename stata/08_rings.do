**************************************************
* 08_rings.do -- Ring specifications: BEVs 5-10 km and 5-15 km away.
* Outputs: donut_regs.tex
* Run via 00_master.do (or run_all.py); standalone runs load _setup.do.
**************************************************
if "$EVC_SETUP" == "" do "_setup.do"

**************************************************
* 9. RING SPECIFICATIONS: BEV ADOPTION AT ALTERNATIVE DISTANCES (Appendix)
*    Through-traffic check: re-estimate the baseline with BEV adoption
*    measured in the 5-10 km and 5-15 km rings around the own-ZIP centroid
*    (2 outcomes x 3 treatment distances, one treatment measure per column).
*    Ring counts exclude the 0-5 km zone that overlaps the outcome catchment.
*    Requires: $INTERMEDIATE/zip_neighbor_pairs.csv (ev_congestion.neighbors)
**************************************************
* --- 9.1. Ring BEV counts by ZIP-year ---
* BEV counts panel (donor side)
use "$INTERMEDIATE/maindata_r5_iv.dta", clear
keep if inrange(year, 2014, 2023)
keep zip_code year count_batteryelectricbev
rename (zip_code count_batteryelectricbev) (neighbor_zip nbr_bev)
tempfile bev_panel
save `bev_panel'

* neighbor pairs from build_zip_neighbors.py
import delimited "$INTERMEDIATE/zip_neighbor_pairs.csv", clear
tempfile pairs
save `pairs'

* expand own-ZIP panel by neighbor pairs, attach neighbor BEV counts
use "$INTERMEDIATE/maindata_r5_iv.dta", clear
keep if inrange(year, 2014, 2023)
keep zip_code year
joinby zip_code using `pairs'
merge m:1 neighbor_zip year using `bev_panel', keep(match) nogen

gen nbr_bev_5_10 = nbr_bev * (dist_km > 5 & dist_km <= 10)  // 5-10 km ring
gen nbr_bev_5_15 = nbr_bev * (dist_km > 5)                  // 5-15 km ring
collapse (sum) nbr_bev_5_10 nbr_bev_5_15, by(zip_code year)
tempfile nbr
save `nbr'

* --- 9.2. Main data with ring regressors ---
use "$INTERMEDIATE/maindata_r5_iv.dta", clear
xtset zip_code year
keep if inrange(year, 2014, 2023)
prep_vars

merge 1:1 zip_code year using `nbr', keep(master match) nogen
gen log_nbr_bev_5_10 = log(nbr_bev_5_10)
gen log_nbr_bev_5_15 = log(nbr_bev_5_15)
label variable log_count_bev    "Log BEV count (own ZIP)"
label variable log_nbr_bev_5_10 "Log BEV count (5--10 km ring)"
label variable log_nbr_bev_5_15 "Log BEV count (5--15 km ring)"

* correlations for the collinearity note in the main text (own vs 5-15: 0.69)
correlate log_count_bev log_nbr_bev_5_10 log_nbr_bev_5_15

* --- 9.3. Regressions: 2 outcomes x 3 treatment distances ---
eststo clear
local m = 0
foreach y in log_weekday_peak_speed_r5 log_weekday_mn_speed_r5 {
    foreach rhs in log_count_bev log_nbr_bev_5_10 log_nbr_bev_5_15 {
        local ++m
        reghdfe `y' `rhs' $controls, absorb(zip_code year) vce(cluster zip_code)
        nzips_add
        estadd scalar adjr2 = e(r2_a)
        estadd local zip_fe  "Yes"
        estadd local year_fe "Yes"
        estadd local control "Yes"
        eststo ring`m'
    }
}

esttab ring1 ring2 ring3 ring4 ring5 ring6 using "$TABLES/donut_regs.tex", ///
    keep(log_count_bev log_nbr_bev_5_10 log_nbr_bev_5_15) ///
    coeflabel(log_count_bev "Log BEV count (own ZIP)" ///
              log_nbr_bev_5_10 "Log BEV count (5--10 km ring)" ///
              log_nbr_bev_5_15 "Log BEV count (5--15 km ring)") ///
    b(%9.4f) se(%9.4f) star(* 0.1 ** 0.05 *** 0.01) ///
    tex label replace ///
    stats(zip_fe year_fe control adjr2 N N_zips, ///
          labels("ZIP fixed effects" "Year fixed effects" "Controls" ///
                 "Adjusted \(R^2\)" "Observations" "ZIP clusters") ///
          fmt(0 0 0 3 0 0)) ///
    nonotes addnotes("\scriptsize \makecell[l]{Note: \sym{*} \(p<0.1\), \sym{**} \(p<0.05\), \sym{***} \(p<0.01\). Standard errors in parentheses are clustered at the ZIP level. \\Outcomes are speed averages within \(r=5\)km of the ZIP centroid. Ring BEV counts sum over ZIP codes whose \\centroids lie in the indicated distance band from the own-ZIP centroid, excluding the own ZIP.}") ///
    nomtitle collabels(none) ///
    mgroups("Log peak-hour speed" "Log midnight speed", ///
            pattern(1 0 0 1 0 0) ///
            prefix(\multicolumn{@span}{c}{) suffix(}) span erepeat(\cmidrule(lr){@span}))
