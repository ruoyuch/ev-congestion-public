**************************************************
* 09_randomization.do -- Permutation test, leave-one-year-out, leave-one-county-out.
* Outputs: permutation_test.pdf, loo_year.pdf, loo_county.pdf
* Run via 00_master.do (or run_all.py); standalone runs load _setup.do.
**************************************************
if "$EVC_SETUP" == "" do "_setup.do"

**************************************************
* 10. RANDOMIZATION ROBUSTNESS (Appendix)
*     Block A: permutation test -- randomly reassign entire ZIP-level BEV
*              adoption paths across ZIP codes (preserves each path's serial
*              structure), re-estimate the baseline TWFE 1,000 times, and
*              compare the true estimate against the placebo distribution.
*     Block B: leave-one-year-out estimates.
*     Block C: leave-one-county-out estimates.
*     Outputs: permutation_test.pdf, loo_year.pdf, loo_county.pdf
**************************************************
set seed $SEED       // paper: 20260704 (set SEED in .env)
local n_perm = $N_PERM  // paper: 1000 (set N_PERM in .env)

use "$INTERMEDIATE/maindata_r5_iv.dta", clear
xtset zip_code year
keep if inrange(year, 2014, 2023)
prep_vars
tempfile master
save `master'

* baseline estimate for reference lines and the permutation p-value
reghdfe log_weekday_peak_speed_r5 log_count_bev $controls, ///
    absorb(zip_code year) vce(cluster zip_code)
scalar b0 = _b[log_count_bev]
display as result "Baseline coefficient: " b0

* --- 10.1. Block A: permutation test ---
* donor file: each ZIP's full treatment path
keep zip_code year log_count_bev
rename (zip_code log_count_bev) (donor_zip bev_perm)
tempfile bevpaths
save `bevpaths'

* base list of ZIPs with stable ids
use `master', clear
keep zip_code
duplicates drop
sort zip_code
gen id = _n
tempfile zipids
save `zipids'

tempfile perm_results
postfile permres int(iter) double(b) using `perm_results'

forvalues i = 1/`n_perm' {
    quietly {
        * random bijection zip_code -> donor_zip
        use `zipids', clear
        gen double u = runiform()
        sort u
        keep zip_code
        rename zip_code donor_zip
        gen id = _n
        tempfile shuf
        save `shuf'
        use `zipids', clear
        merge 1:1 id using `shuf', nogen
        keep zip_code donor_zip
        tempfile map
        save `map'

        * assign permuted adoption paths and re-estimate
        use `master', clear
        merge m:1 zip_code using `map', keep(master match) nogen
        merge 1:1 donor_zip year using `bevpaths', keep(master match) nogen
        reghdfe log_weekday_peak_speed_r5 bev_perm $controls, ///
            absorb(zip_code year) vce(cluster zip_code)
        post permres (`i') (_b[bev_perm])
    }
    if mod(`i', 100) == 0 display as text "  permutation `i'/`n_perm' done"
}
postclose permres

use `perm_results', clear
gen extreme = abs(b) >= abs(b0)
quietly sum extreme
local pval = string(r(mean), "%5.3f")
local bmin = -0.012   // hardcoded axis range so the true-estimate line is visible
local bmax = 0.012
display as result "Permutation p-value (|b_perm| >= |b_actual|): `pval'"

twoway (histogram b, width(0.0005) color(navy%50) lcolor(navy)) ///
    , xline(`=b0', lcolor(cranberry) lwidth(medthick)) ///
    xscale(range(`bmin' `bmax')) ///
    xlabel(`bmin'(0.004)`bmax', format(%6.3f)) ///
    xtitle("Placebo coefficient (permuted BEV adoption paths)") ///
    ytitle("Density") ///
    note("True estimate (vertical line): `=string(b0, "%6.4f")'. Permutation p-value: `pval' (`n_perm' draws).") ///
    legend(off) scheme(s1color)
graph export "$FIGURES/permutation_test.pdf", replace

* --- 10.2. Block B: leave-one-year-out ---
use `master', clear
tempfile loo_year_results
postfile looyr int(year_excl) double(b lb ub) using `loo_year_results'
levelsof year, local(years)
foreach y of local years {
    quietly reghdfe log_weekday_peak_speed_r5 log_count_bev $controls ///
        if year != `y', absorb(zip_code year) vce(cluster zip_code)
    post looyr (`y') (_b[log_count_bev]) ///
        (_b[log_count_bev] - 1.96*_se[log_count_bev]) ///
        (_b[log_count_bev] + 1.96*_se[log_count_bev])
}
postclose looyr

use `loo_year_results', clear
twoway (rcap lb ub year_excl, lcolor(navy)) ///
    (scatter b year_excl, mcolor(navy) msymbol(circle)) ///
    , yline(0, lcolor(gs8) lpattern(solid)) ///
    yline(`=b0', lcolor(cranberry) lpattern(shortdash)) ///
    xtitle("Excluded year") ytitle("Coefficient on log BEV count") ///
    xlabel(2014(1)2023, angle(45)) ///
    note("Dashed line: full-sample estimate. Bars: 95% confidence intervals.") ///
    legend(off) scheme(s1color)
graph export "$FIGURES/loo_year.pdf", replace

* --- 10.3. Block C: leave-one-county-out ---
* county_code_fe is already encoded in maindata_r5_iv (Section 1.3)
use `master', clear
tempfile loo_cty_results
postfile loocty int(county_id) double(b lb ub) using `loo_cty_results'
levelsof county_code_fe, local(counties)
foreach c of local counties {
    quietly reghdfe log_weekday_peak_speed_r5 log_count_bev $controls ///
        if county_code_fe != `c', absorb(zip_code year) vce(cluster zip_code)
    post loocty (`c') (_b[log_count_bev]) ///
        (_b[log_count_bev] - 1.96*_se[log_count_bev]) ///
        (_b[log_count_bev] + 1.96*_se[log_count_bev])
}
postclose loocty

use `loo_cty_results', clear
sort b
gen rank = _n
twoway (rcap lb ub rank, lcolor(navy%60)) ///
    (scatter b rank, mcolor(navy) msymbol(circle) msize(small)) ///
    , yline(0, lcolor(gs8) lpattern(solid)) ///
    yline(`=b0', lcolor(cranberry) lpattern(shortdash)) ///
    xtitle("Excluded county (ranked by coefficient)") ///
    ytitle("Coefficient on log BEV count") ///
    note("Dashed line: full-sample estimate. Bars: 95% confidence intervals.") ///
    legend(off) scheme(s1color)
graph export "$FIGURES/loo_county.pdf", replace

display as result "Done. Outputs: donut_regs.tex, permutation_test.pdf, loo_year.pdf, loo_county.pdf"
