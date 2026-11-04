**************************************************
* 06_iv.do -- IV first stage and binned event study of the CVRP instrument.
* Outputs: cvrp_iv_table.tex, cvrp_bin_es_fs.pdf
* Run via 00_master.do (or run_all.py); standalone runs load _setup.do.
**************************************************
if "$EVC_SETUP" == "" do "_setup.do"

**************************************************
* 7. IV FIRST STAGE TABLE AND EVENT STUDY (Appendix)
**************************************************
use "$INTERMEDIATE/maindata_r5_iv.dta", clear
xtset zip_code year
keep if inrange(year, 2014, 2023)

prep_vars

eststo clear

* --- 7.1. First stage table ---
* Identify the exact sample used by the 2SLS in Table 1 (peak-hour speed, 2WFE)
quietly ivreghdfe log_weekday_peak_speed_r5 $controls ///
    (log_count_bev = z_cap_100), absorb(zip_code year) cluster(zip_code)
gen byte iv_sample = e(sample)

* First stage restricted to that sample
reghdfe log_count_bev z_cap_100 $controls if iv_sample, ///
    absorb(zip_code year) vce(cluster zip_code)
estadd scalar adjr2 = e(r2_a)
test z_cap_100
estadd scalar Fstat = r(F)
nzips_add
estadd local zip_fe  "Yes"
estadd local year_fe "Yes"
estadd local cy_fe   "No"
eststo iv1

esttab iv1 using "$TABLES/cvrp_iv_table.tex", ///
    keep(z_cap_100) ///
    coeflabel(z_cap_100 "High-income share × post-2016") ///
    b(%9.4f) se(%9.4f) star(* 0.10 ** 0.05 *** 0.01) tex label replace ///
    stats(zip_fe year_fe cy_fe adjr2 N N_zips Fstat, ///
          labels("ZIP fixed effects" "Year fixed effects" "County-year fixed effects" ///
                 "Adjusted \(R^2\)" "Observations" "ZIP clusters" "\textit{F}-stat (instrument)") ///
          fmt(0 0 0 3 0 0 2)) ///
    nonotes addnotes("\scriptsize \makecell[l]{Note: \sym{*} \(p<0.1\), \sym{**} \(p<0.05\), \sym{***} \(p<0.01\). SEs clustered at ZIP level. \\High-income share is the ZIP-level share of households with 100k+ annual income. \\ According to the CVRP income eligibility rule, a higher share will reduce policy incentive.}") ///
    collabels(none) mtitle("Log BEV count")

* --- 7.2. First stage event study ---
gen rel2017 = year - 2017

forvalues k = 3(-1)2 {
    gen cvrp_cap_tm`k' = pre_cvrp_above_100k * (rel2017 == -`k')
}
forvalues k = 0/6 {
    gen cvrp_cap_tp`k' = pre_cvrp_above_100k * (rel2017 == `k')
}

local cap_terms cvrp_cap_tm3 cvrp_cap_tm2 ///
                cvrp_cap_tp0 cvrp_cap_tp1 cvrp_cap_tp2 ///
                cvrp_cap_tp3 cvrp_cap_tp4 cvrp_cap_tp5 cvrp_cap_tp6

reghdfe log_count_bev `cap_terms' $controls if iv_sample, ///
    absorb(zip_code year) vce(cluster zip_code)

test cvrp_cap_tm3 cvrp_cap_tm2
local p_pre : display %5.3f r(p)
coefplot, ///
    keep(`cap_terms') vertical yline(0, lcolor(red)) ///
    rename(cvrp_cap_tm3=-3 cvrp_cap_tm2=-2 ///
           cvrp_cap_tp0=0  cvrp_cap_tp1=1  cvrp_cap_tp2=2 ///
           cvrp_cap_tp3=3  cvrp_cap_tp4=4  cvrp_cap_tp5=5 cvrp_cap_tp6=6) ///
    xlabel(1 "-3" 2 "-2" 3 "0" 4 "1" 5 "2" 6 "3" 7 "4" 8 "5" 9 "6") ///
    xtitle("Years relative to CVRP income reform") ///
    ytitle("Effect on log BEV count") ///
    note("Reference year: 2016.") ///
    ciopts(recast(rcap)) mcolor(navy) ///
    graphregion(color(white)) plotregion(color(white)) ///
    name(es_fs_cap, replace)
graph export "$FIGURES/cvrp_bin_es_fs.pdf", replace
