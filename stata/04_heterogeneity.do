**************************************************
* 04_heterogeneity.do -- Split-sample heterogeneity by four moderators.
* Outputs: heterogeneity_split*.pdf
* Run via 00_master.do (or run_all.py); standalone runs load _setup.do.
**************************************************
if "$EVC_SETUP" == "" do "_setup.do"

**************************************************
* 5. HETEROGENEITY ANALYSIS
*    Grouped bar chart: low vs. high (pre-2017 median split), 6 moderators
*    Outcome: log weekday peak-hour speed, r=5km (2WFE)
**************************************************
use "$INTERMEDIATE/maindata_with_radius.dta", clear
xtset zip_code year
keep if inrange(year, 2014, 2023)

prep_vars

local mod_vars "hh_median_income pop_density pct_pt evcs_pc"

* Pre-period (2014-2016) ZIP average for each moderator — exogenous split
foreach U of local mod_vars {
    gen pre_raw_`U' = `U' if inrange(year, 2014, 2016)
    bysort zip_code: egen pre_`U' = mean(pre_raw_`U')
    drop pre_raw_`U'
}

* Compute ZIP-level median and assign hi/lo (one obs per ZIP for median)
bysort zip_code (year): gen _zip1 = (_n == 1)
foreach U of local mod_vars {
    quietly sum pre_`U' if _zip1, detail
    local med_`U' = r(p50)
    gen hi_`U' = (pre_`U' > `med_`U'') if !missing(pre_`U')
}
drop _zip1

* Main estimate (r=5km OLS 2WFE) for reference line
quietly reghdfe log_weekday_peak_speed_r5 log_count_bev $controls, ///
    absorb(zip_code year) vce(cluster zip_code)
local main_est = _b[log_count_bev]

* Collect low/high estimates for each moderator
tempfile het_results
capture postutil clear
postfile het_h int mod_num int grp double coef double lb double ub ///
    using `het_results'

local i = 1
foreach U of local mod_vars {
    * Low group
    quietly reghdfe log_weekday_peak_speed_r5 log_count_bev $controls ///
        if hi_`U' == 0, absorb(zip_code year) vce(cluster zip_code)
    local b = _b[log_count_bev]
    local s = _se[log_count_bev]
    post het_h (`i') (0) (`b') (`b' - 1.96*`s') (`b' + 1.96*`s')

    * High group
    quietly reghdfe log_weekday_peak_speed_r5 log_count_bev $controls ///
        if hi_`U' == 1, absorb(zip_code year) vce(cluster zip_code)
    local b = _b[log_count_bev]
    local s = _se[log_count_bev]
    post het_h (`i') (1) (`b') (`b' - 1.96*`s') (`b' + 1.96*`s')

    local i = `i' + 1
}
postclose het_h

* Plot
use `het_results', clear
gen x_pos = mod_num - 0.22 + grp * 0.44

* Headroom above the tallest error bar so the inside legend does not overlap
quietly sum lb
local ymin = min(r(min), 0)
quietly sum ub
local ytop = r(max) + 0.35 * (r(max) - `ymin')

twoway ///
    (bar coef x_pos if grp == 0, barwidth(0.38) ///
        fcolor("0 70 127%70") lcolor(none)) ///
    (bar coef x_pos if grp == 1, barwidth(0.38) ///
        fcolor("215 96 0%70") lcolor(none)) ///
    (rcap ub lb x_pos if grp == 0, lcolor("0 70 127") lwidth(thin)) ///
    (rcap ub lb x_pos if grp == 1, lcolor("215 96 0") lwidth(thin)) ///
    , ///
    yline(0, lcolor(black) lwidth(thin)) ///
    yline(`main_est', lcolor(black) lwidth(thin) lpattern(shortdash)) ///
    xlabel(1 "Household income" 2 "Population density" 3 "Transit commuter share" 4 "BEV chargers", ///
           labsize(med) angle(45) noticks) ///
    ylabel(, format(%5.4f) labsize(med) angle(0)) ///
    yscale(range(`ymin' `ytop')) ///
    ytitle("Coefficient", size(med)) ///
    xtitle("") ///
    legend(order(1 "Below median" 2 "Above median") size(med) ///
           ring(0) position(1) rows(2) region(lcolor(none))) ///
    graphregion(color(white)) plotregion(color(white)) ///
    xsize(5) ysize(4)
graph export "$FIGURES/heterogeneity_split.pdf", replace


* ============================================================
* 5B. MECHANISM HETEROGENEITY: VEHICLE OWNERSHIP & TRAFFIC FLOW
*     Same ZIP-level panel; ownership uses D. operator on total vehicles
* ============================================================
use "$INTERMEDIATE/maindata_with_radius.dta", clear
xtset zip_code year
keep if inrange(year, 2014, 2023)

prep_vars
gen count_total               = count_batteryelectricbev / proportion_batteryelectricbev
gen log_count_total           = log(count_total)
gen d_log_count_bev           = D.log_count_bev
gen log_weekday_avg_hourly_flow = log(weekday_all_day_avg_hourly_flow)

local mod_vars "hh_median_income pop_density pct_pt evcs_pc"

foreach U of local mod_vars {
    gen pre_raw_`U' = `U' if inrange(year, 2014, 2016)
    bysort zip_code: egen pre_`U' = mean(pre_raw_`U')
    drop pre_raw_`U'
}
bysort zip_code (year): gen _zip1 = (_n == 1)
foreach U of local mod_vars {
    quietly sum pre_`U' if _zip1, detail
    local med_`U' = r(p50)
    gen hi_`U' = (pre_`U' > `med_`U'') if !missing(pre_`U')
}
drop _zip1

* --- Ownership ---
quietly reghdfe D.log_count_total d_log_count_bev $controls, ///
    absorb(zip_code year) vce(cluster zip_code)
local main_own = _b[d_log_count_bev]

tempfile het_own
capture postutil clear
postfile het_h int mod_num int grp double coef double lb double ub using `het_own'

local i = 1
foreach U of local mod_vars {
    quietly reghdfe D.log_count_total d_log_count_bev $controls if hi_`U' == 0, ///
        absorb(zip_code year) vce(cluster zip_code)
    local b = _b[d_log_count_bev]
    local s = _se[d_log_count_bev]
    post het_h (`i') (0) (`b') (`b' - 1.96*`s') (`b' + 1.96*`s')

    quietly reghdfe D.log_count_total d_log_count_bev $controls if hi_`U' == 1, ///
        absorb(zip_code year) vce(cluster zip_code)
    local b = _b[d_log_count_bev]
    local s = _se[d_log_count_bev]
    post het_h (`i') (1) (`b') (`b' - 1.96*`s') (`b' + 1.96*`s')

    local i = `i' + 1
}
postclose het_h

preserve
use `het_own', clear
gen x_pos = mod_num - 0.22 + grp * 0.44

* Headroom above the tallest error bar so the inside legend does not overlap
quietly sum lb
local ymin = min(r(min), 0)
quietly sum ub
local ytop = r(max) + 0.35 * (r(max) - `ymin')
twoway ///
    (bar coef x_pos if grp == 0, barwidth(0.38) fcolor("0 70 127%70") lcolor(none)) ///
    (bar coef x_pos if grp == 1, barwidth(0.38) fcolor("215 96 0%70") lcolor(none)) ///
    (rcap ub lb x_pos if grp == 0, lcolor("0 70 127") lwidth(thin)) ///
    (rcap ub lb x_pos if grp == 1, lcolor("215 96 0") lwidth(thin)) ///
    , ///
    yline(0, lcolor(black) lwidth(thin)) ///
    yline(`main_own', lcolor(black) lwidth(thin) lpattern(shortdash)) ///
    xlabel(1 "Household income" 2 "Population density" 3 "Transit commuter share" 4 "BEV chargers", ///
           labsize(med) angle(45) noticks) ///
    ylabel(, format(%5.4f) labsize(med) angle(0)) ///
    yscale(range(`ymin' `ytop')) ///
    ytitle("Coefficient", size(med)) xtitle("") ///
    legend(order(1 "Below median" 2 "Above median") size(med) ///
           ring(0) position(1) rows(2) region(lcolor(none))) ///
    graphregion(color(white)) plotregion(color(white)) ///
    xsize(5) ysize(4)
graph export "$FIGURES/heterogeneity_split_ownership.pdf", replace
restore

* --- Traffic flow ---
quietly reghdfe log_weekday_avg_hourly_flow log_count_bev $controls, ///
    absorb(zip_code year) vce(cluster zip_code)
local main_flow = _b[log_count_bev]

tempfile het_flow
capture postutil clear
postfile het_h int mod_num int grp double coef double lb double ub using `het_flow'

local i = 1
foreach U of local mod_vars {
    quietly reghdfe log_weekday_avg_hourly_flow log_count_bev $controls if hi_`U' == 0, ///
        absorb(zip_code year) vce(cluster zip_code)
    local b = _b[log_count_bev]
    local s = _se[log_count_bev]
    post het_h (`i') (0) (`b') (`b' - 1.96*`s') (`b' + 1.96*`s')

    quietly reghdfe log_weekday_avg_hourly_flow log_count_bev $controls if hi_`U' == 1, ///
        absorb(zip_code year) vce(cluster zip_code)
    local b = _b[log_count_bev]
    local s = _se[log_count_bev]
    post het_h (`i') (1) (`b') (`b' - 1.96*`s') (`b' + 1.96*`s')

    local i = `i' + 1
}
postclose het_h

use `het_flow', clear
gen x_pos = mod_num - 0.22 + grp * 0.44

* Headroom above the tallest error bar so the inside legend does not overlap
quietly sum lb
local ymin = min(r(min), 0)
quietly sum ub
local ytop = r(max) + 0.35 * (r(max) - `ymin')
twoway ///
    (bar coef x_pos if grp == 0, barwidth(0.38) fcolor("0 70 127%70") lcolor(none)) ///
    (bar coef x_pos if grp == 1, barwidth(0.38) fcolor("215 96 0%70") lcolor(none)) ///
    (rcap ub lb x_pos if grp == 0, lcolor("0 70 127") lwidth(thin)) ///
    (rcap ub lb x_pos if grp == 1, lcolor("215 96 0") lwidth(thin)) ///
    , ///
    yline(0, lcolor(black) lwidth(thin)) ///
    yline(`main_flow', lcolor(black) lwidth(thin) lpattern(shortdash)) ///
    xlabel(1 "Household income" 2 "Population density" 3 "Transit commuter share" 4 "BEV chargers", ///
           labsize(med) angle(45) noticks) ///
    ylabel(, format(%5.4f) labsize(med) angle(0)) ///
    yscale(range(`ymin' `ytop')) ///
    ytitle("Coefficient", size(med)) xtitle("") ///
    legend(order(1 "Below median" 2 "Above median") size(med) ///
           ring(0) position(1) rows(2) region(lcolor(none))) ///
    graphregion(color(white)) plotregion(color(white)) ///
    xsize(5) ysize(4)
graph export "$FIGURES/heterogeneity_split_flow.pdf", replace


* ============================================================
* 5C. MECHANISM HETEROGENEITY: PUBLIC TRANSIT RIDERSHIP (UA level)
*     ~35 UAs only — estimates will be wider than ZIP-level analyses
* ============================================================
use "$INTERMEDIATE/uantddata.dta", clear
xtset ua year
keep if inrange(year, 2014, 2023)

local mod_vars "hh_median_income pop_density pct_pt evcs_pc"

foreach U of local mod_vars {
    gen pre_raw_`U' = `U' if inrange(year, 2014, 2016)
    bysort ua: egen pre_`U' = mean(pre_raw_`U')
    drop pre_raw_`U'
}
bysort ua (year): gen _ua1 = (_n == 1)
foreach U of local mod_vars {
    quietly sum pre_`U' if _ua1, detail
    local med_`U' = r(p50)
    gen hi_`U' = (pre_`U' > `med_`U'') if !missing(pre_`U')
}
drop _ua1

quietly reghdfe log_pt_ridership log_count_bev $controls, ///
    absorb(ua year) vce(cluster ua)
local main_pt = _b[log_count_bev]

tempfile het_pt
capture postutil clear
postfile het_h int mod_num int grp double coef double lb double ub using `het_pt'

local i = 1
foreach U of local mod_vars {
    quietly reghdfe log_pt_ridership log_count_bev $controls if hi_`U' == 0, ///
        absorb(ua year) vce(cluster ua)
    local b = _b[log_count_bev]
    local s = _se[log_count_bev]
    post het_h (`i') (0) (`b') (`b' - 1.96*`s') (`b' + 1.96*`s')

    quietly reghdfe log_pt_ridership log_count_bev $controls if hi_`U' == 1, ///
        absorb(ua year) vce(cluster ua)
    local b = _b[log_count_bev]
    local s = _se[log_count_bev]
    post het_h (`i') (1) (`b') (`b' - 1.96*`s') (`b' + 1.96*`s')

    local i = `i' + 1
}
postclose het_h

use `het_pt', clear
gen x_pos = mod_num - 0.22 + grp * 0.44

* Headroom above the tallest error bar so the inside legend does not overlap
quietly sum lb
local ymin = min(r(min), 0)
quietly sum ub
local ytop = r(max) + 0.35 * (r(max) - `ymin')
twoway ///
    (bar coef x_pos if grp == 0, barwidth(0.38) fcolor("0 70 127%70") lcolor(none)) ///
    (bar coef x_pos if grp == 1, barwidth(0.38) fcolor("215 96 0%70") lcolor(none)) ///
    (rcap ub lb x_pos if grp == 0, lcolor("0 70 127") lwidth(thin)) ///
    (rcap ub lb x_pos if grp == 1, lcolor("215 96 0") lwidth(thin)) ///
    , ///
    yline(0, lcolor(black) lwidth(thin)) ///
    yline(`main_pt', lcolor(black) lwidth(thin) lpattern(shortdash)) ///
    xlabel(1 "Household income" 2 "Population density" 3 "Transit commuter share" 4 "BEV chargers", ///
           labsize(med) angle(45) noticks) ///
    ylabel(, format(%5.3f) labsize(med) angle(0)) ///
    yscale(range(`ymin' `ytop')) ///
    ytitle("Coefficient", size(med)) xtitle("") ///
    legend(order(1 "Below median" 2 "Above median") size(med) ///
           ring(0) position(1) rows(2) region(lcolor(none))) ///
    graphregion(color(white)) plotregion(color(white)) ///
    xsize(5) ysize(4)
graph export "$FIGURES/heterogeneity_split_pt.pdf", replace
