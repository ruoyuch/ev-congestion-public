**************************************************
* 03_spatial_scale.do -- Coefficients by radius (1-15 km), peak and midnight.
* Outputs: spillover_radius_effects_speed_weekday_peak.pdf, ..._mid_night.pdf
* Run via 00_master.do (or run_all.py); standalone runs load _setup.do.
**************************************************
if "$EVC_SETUP" == "" do "_setup.do"

**************************************************
* 4. SPATIAL SPILLOVER AS ROBUSTNESS CHECK
**************************************************
** A **
use "$INTERMEDIATE/maindata_with_radius.dta", clear
xtset zip_code year
keep if inrange(year, 2014, 2023) // keep data from 2014-2023, our study period

prep_vars


* create a temporary file to store results
tempfile results
capture postutil clear
postfile handle str10 radius double coef double se double p ///
        double lb double ub using `results'


* loop over radii 1–15 km
forvalues r = 1/15 {

    local depvar = "weekday_peak_weighted_speed_r`r'"   // NOTE: Python created rXkm suffix

    capture confirm variable `depvar'
    if _rc {
        di as error "Variable `depvar' not found — skipping radius `r' km."
        continue
    }

    gen log_speed_r`r' = log(`depvar')

    reghdfe log_speed_r`r' log_count_bev $controls, ///
        absorb(zip_code year) vce(cluster zip_code)

    * extract results
    local b  = _b[log_count_bev]
    local se = _se[log_count_bev]
    local p  = 2*normal(-abs(`b'/`se'))
    local lb = `b' - 1.96*`se'
    local ub = `b' + 1.96*`se'

    post handle ("`r'") (`b') (`se') (`p') (`lb') (`ub')

    drop log_speed_r`r'
}

postclose handle

* save clean spillover result dataset for plotting
use `results', clear
gen radius_km = real(radius)
order radius_km coef se lb ub p
sort radius_km
save "$INTERMEDIATE/spillover_radius_results.dta", replace

* plot
use "$INTERMEDIATE/spillover_radius_results.dta", clear
sort radius_km
twoway ///
    (rcap ub lb radius_km if radius_km != 5, lcolor("0 70 127%60") lwidth(thin)) ///
    (rcap ub lb radius_km if radius_km == 5, lcolor("215 96 0") lwidth(thin)) ///
    (scatter coef radius_km if radius_km != 5, msymbol(O) msize(small) mcolor("0 70 127")) ///
    (scatter coef radius_km if radius_km == 5, msymbol(O) msize(medium) mcolor("215 96 0")) ///
    , ///
    yline(0, lcolor(black) lwidth(thin)) ///
    xlabel(1(1)15, labsize(med)) ///
    ytitle("Coefficient", size(med)) ///
    xtitle("Effect radius (km)", size(med)) ///
    ylabel(-0.03(0.01)0.02, format(%5.4f) labsize(med) angle(0)) ///
    legend(off) ///
    graphregion(color(white)) plotregion(color(white)) ///
    xsize(4) ysize(3)
graph export "$FIGURES/spillover_radius_effects_speed_weekday_peak.pdf", replace


** B **
use "$INTERMEDIATE/maindata_with_radius.dta", clear
xtset zip_code year
keep if inrange(year, 2014, 2023) // keep data from 2014-2023, our study period

prep_vars

* create a temporary file to store results
tempfile results
capture postutil clear
postfile handle str10 radius double coef double se double p ///
        double lb double ub using `results'


* loop over radii 1–15 km
forvalues r = 1/15 {

    local depvar = "weekday_mn_weighted_speed_r`r'"   // NOTE: Python created rXkm suffix

    capture confirm variable `depvar'
    if _rc {
        di as error "Variable `depvar' not found — skipping radius `r' km."
        continue
    }

    gen log_speed_r`r' = log(`depvar')

    reghdfe log_speed_r`r' log_count_bev $controls, ///
        absorb(zip_code year) vce(cluster zip_code)

    * extract results
    local b  = _b[log_count_bev]
    local se = _se[log_count_bev]
    local p  = 2*normal(-abs(`b'/`se'))
    local lb = `b' - 1.96*`se'
    local ub = `b' + 1.96*`se'

    post handle ("`r'") (`b') (`se') (`p') (`lb') (`ub')

    drop log_speed_r`r'
}

postclose handle

* save clean spillover result dataset for plotting
use `results', clear
gen radius_km = real(radius)
order radius_km coef se lb ub p
sort radius_km
save "$INTERMEDIATE/spillover_radius_results_mn.dta", replace

* plot
use "$INTERMEDIATE/spillover_radius_results_mn.dta", clear
sort radius_km
twoway ///
    (rcap ub lb radius_km if radius_km != 5, lcolor("0 70 127%60") lwidth(thin)) ///
    (rcap ub lb radius_km if radius_km == 5, lcolor("215 96 0") lwidth(thin)) ///
    (scatter coef radius_km if radius_km != 5, msymbol(O) msize(small) mcolor("0 70 127")) ///
    (scatter coef radius_km if radius_km == 5, msymbol(O) msize(medium) mcolor("215 96 0")) ///
    , ///
    yline(0, lcolor(black) lwidth(thin)) ///
    xlabel(1(1)15, labsize(med)) ///
    xtitle("Effect radius (km)", size(med)) ///
    ytitle("Coefficient", size(med)) ///
    ylabel(, format(%5.4f) labsize(med) angle(0)) ///
    legend(off) ///
    graphregion(color(white)) plotregion(color(white)) ///
    xsize(4) ysize(3)
graph export "$FIGURES/spillover_radius_effects_speed_weekday_mid_night.pdf", replace
