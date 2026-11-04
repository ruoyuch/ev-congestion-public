**************************************************
* 10_fe_robustness.do -- ZIP + county-year FE, county/ZIP trends, excluding 2020-21.
* Outputs: twfe_speed_regs_robust_peak.tex, twfe_speed_regs_robust_mn.tex
* Run via 00_master.do (or run_all.py); standalone runs load _setup.do.
**************************************************
if "$EVC_SETUP" == "" do "_setup.do"

**************************************************
* 11. FIXED-EFFECT AND SAMPLE ROBUSTNESS (Appendix)
*     Peak (Panel A) and midnight placebo (Panel B), 5 cols each:
*     (1) ZIP + county-year FE | (2) ZIP + year FE + county linear trends
*     (3) 2WFE excl. 2020-21   | (4) ZIP + county-year FE excl. 2020-21
*     (5) ZIP + year FE + ZIP linear trends
*     Outputs: twfe_speed_regs_robust_peak.tex, twfe_speed_regs_robust_mn.tex
**************************************************
use "$INTERMEDIATE/maindata_r5_iv.dta", clear
xtset zip_code year
keep if inrange(year, 2014, 2023)
prep_vars

foreach out in peak mn {
    eststo clear

    * (1) ZIP + county-year FE
    reghdfe log_weekday_`out'_speed_r5 log_count_bev $controls, ///
        absorb(zip_code county_year_fe) vce(cluster zip_code)
    nzips_add
    estadd scalar adjr2 = e(r2_a)
    estadd local zip_fe   "Yes"
    estadd local cy_fe    "Yes"
    estadd local c_trend  "No"
    estadd local z_trend  "No"
    estadd local sample   "2014--2023"
    eststo rob1

    * (2) ZIP + year FE + county-specific linear trends
    reghdfe log_weekday_`out'_speed_r5 log_count_bev $controls, ///
        absorb(zip_code year county_code_fe#c.year) vce(cluster zip_code)
    nzips_add
    estadd scalar adjr2 = e(r2_a)
    estadd local zip_fe   "Yes"
    estadd local cy_fe    "No"
    estadd local c_trend  "Yes"
    estadd local z_trend  "No"
    estadd local sample   "2014--2023"
    eststo rob2

    * (3) 2WFE, excl. 2020-21
    reghdfe log_weekday_`out'_speed_r5 log_count_bev $controls ///
        if !inlist(year, 2020, 2021), ///
        absorb(zip_code year) vce(cluster zip_code)
    nzips_add
    estadd scalar adjr2 = e(r2_a)
    estadd local zip_fe   "Yes"
    estadd local cy_fe    "No"
    estadd local c_trend  "No"
    estadd local z_trend  "No"
    estadd local sample   "Excl. 2020--21"
    eststo rob3

    * (4) ZIP + county-year FE, excl. 2020-21
    reghdfe log_weekday_`out'_speed_r5 log_count_bev $controls ///
        if !inlist(year, 2020, 2021), ///
        absorb(zip_code county_year_fe) vce(cluster zip_code)
    nzips_add
    estadd scalar adjr2 = e(r2_a)
    estadd local zip_fe   "Yes"
    estadd local cy_fe    "Yes"
    estadd local c_trend  "No"
    estadd local z_trend  "No"
    estadd local sample   "Excl. 2020--21"
    eststo rob4

    * (5) ZIP + year FE + ZIP-specific linear trends
    reghdfe log_weekday_`out'_speed_r5 log_count_bev $controls, ///
        absorb(zip_code##c.year year) vce(cluster zip_code)
    nzips_add
    estadd scalar adjr2 = e(r2_a)
    estadd local zip_fe   "Yes"
    estadd local cy_fe    "No"
    estadd local c_trend  "No"
    estadd local z_trend  "Yes"
    estadd local sample   "2014--2023"
    eststo rob5

    if "`out'" == "peak" local ylab "Log peak-hour speed"
    else                 local ylab "Log midnight speed"

    esttab rob1 rob2 rob3 rob4 rob5 ///
        using "$TABLES/twfe_speed_regs_robust_`out'.tex", ///
        keep(log_count_bev) coeflabel(log_count_bev "Log BEV count") ///
        b(%9.4f) se(%9.4f) star(* 0.10 ** 0.05 *** 0.01) ///
        tex label replace ///
        stats(zip_fe cy_fe c_trend z_trend sample adjr2 N N_zips, ///
              labels("ZIP fixed effects" "County-year fixed effects" ///
                     "County linear trends" "ZIP linear trends" "Sample years" ///
                     "Adjusted \(R^2\)" "Observations" "ZIP clusters") ///
              fmt(0 0 0 0 0 3 0 0)) ///
        nonotes nomtitle collabels(none) ///
        mgroups("`ylab'", ///
                pattern(1 0 0 0 0) ///
                prefix(\multicolumn{@span}{c}{) suffix(}) span erepeat(\cmidrule(lr){@span}))
}

display as result "Done. Outputs: twfe_speed_regs_robust_peak.tex, twfe_speed_regs_robust_mn.tex"
