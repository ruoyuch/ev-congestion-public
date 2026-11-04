**************************************************
* 07_covid.do -- COVID-period robustness.
* Outputs: twfe_speed_regs_covid.tex
* Run via 00_master.do (or run_all.py); standalone runs load _setup.do.
**************************************************
if "$EVC_SETUP" == "" do "_setup.do"

**************************************************
* 8. COVID ROBUSTNESS CHECK (Appendix)
*    Peak-hour speed, 6 cols: 2WFE / County-year FE / 2SLS × excl.2020 / 2014-2020
**************************************************
use "$INTERMEDIATE/maindata_r5_iv.dta", clear
xtset zip_code year
keep if inrange(year, 2014, 2023)

prep_vars

eststo clear

* (1) 2WFE, excl. 2020
reghdfe log_weekday_peak_speed_r5 log_count_bev $controls if year != 2020, ///
    absorb(zip_code year) vce(cluster zip_code)
nzips_add
estadd scalar adjr2 = e(r2_a)
estadd local year_fe "Yes"
estadd local zip_fe  "Yes"
estadd local cy_fe   "No"
estadd local control "Yes"
estadd local sample  "Excl. 2020"
eststo cov1

* (2) 2WFE, 2014-2020
reghdfe log_weekday_peak_speed_r5 log_count_bev $controls if year <= 2020, ///
    absorb(zip_code year) vce(cluster zip_code)
nzips_add
estadd scalar adjr2 = e(r2_a)
estadd local year_fe "Yes"
estadd local zip_fe  "Yes"
estadd local cy_fe   "No"
estadd local control "Yes"
estadd local sample  "2014--2020"
eststo cov2

* (3) County-year FE, excl. 2020
reghdfe log_weekday_peak_speed_r5 log_count_bev $controls if year != 2020, ///
    absorb(county_year_fe) vce(cluster zip_code)
nzips_add
estadd scalar adjr2 = e(r2_a)
estadd local year_fe "No"
estadd local zip_fe  "No"
estadd local cy_fe   "Yes"
estadd local control "Yes"
estadd local sample  "Excl. 2020"
eststo cov3

* (4) County-year FE, 2014-2020
reghdfe log_weekday_peak_speed_r5 log_count_bev $controls if year <= 2020, ///
    absorb(county_year_fe) vce(cluster zip_code)
nzips_add
estadd scalar adjr2 = e(r2_a)
estadd local year_fe "No"
estadd local zip_fe  "No"
estadd local cy_fe   "Yes"
estadd local control "Yes"
estadd local sample  "2014--2020"
eststo cov4

* (5) 2SLS, excl. 2020
ivreghdfe log_weekday_peak_speed_r5 $controls ///
    (log_count_bev = z_cap_100) if year != 2020, ///
    absorb(zip_code year) cluster(zip_code)
estadd scalar Fstat = e(widstat)
nzips_add
estadd local year_fe "Yes"
estadd local zip_fe  "Yes"
estadd local cy_fe   "No"
estadd local control "Yes"
estadd local sample  "Excl. 2020"
eststo cov5

* (6) 2SLS, 2014-2020
ivreghdfe log_weekday_peak_speed_r5 $controls ///
    (log_count_bev = z_cap_100) if year <= 2020, ///
    absorb(zip_code year) cluster(zip_code)
estadd scalar Fstat = e(widstat)
nzips_add
estadd local year_fe "Yes"
estadd local zip_fe  "Yes"
estadd local cy_fe   "No"
estadd local control "Yes"
estadd local sample  "2014--2020"
eststo cov6

esttab cov1 cov2 cov3 cov4 cov5 cov6 ///
    using "$TABLES/twfe_speed_regs_covid.tex", ///
    keep(log_count_bev) coeflabel(log_count_bev "Log BEV count") ///
    b(%9.4f) se(%9.4f) star(* 0.10 ** 0.05 *** 0.01) ///
    tex label replace ///
    stats(year_fe zip_fe cy_fe control sample adjr2 N N_zips Fstat, ///
          labels("Year fixed effects" "ZIP fixed effects" "County-year fixed effects" ///
                 "Controls" "Sample years" "Adjusted \(R^2\)" "Observations" "ZIP clusters" ///
                 "\textit{F}-stat (instrument)") ///
          fmt(0 0 0 0 0 3 0 0 2)) ///
    nonotes addnotes("\scriptsize \makecell[l]{Note: \sym{*} \(p<0.1\), \sym{**} \(p<0.05\), \sym{***} \(p<0.01\). \\Standard errors in parentheses are clustered at the ZIP level. \\The peak-hour speed is calculated within \(r=5\)km of the ZIP centroid. \\The full 2014--2023 sample results are reported in the main text.}") ///
    nomtitle collabels(none) ///
    mgroups("Log peak-hour speed", ///
            pattern(1 0 0 0 0 0) ///
            prefix(\multicolumn{@span}{c}{) suffix(}) span erepeat(\cmidrule(lr){@span}))
