**************************************************
* 05_lagged.do -- Lagged BEV counts (reverse causality check).
* Outputs: twfe_speed_regs_lag.tex
* Run via 00_master.do (or run_all.py); standalone runs load _setup.do.
**************************************************
if "$EVC_SETUP" == "" do "_setup.do"

**************************************************
* 6. LAGGED REGRESSIONS TO RULE OUT REVERSE CAUSALITY
**************************************************
use "$INTERMEDIATE/maindata_with_radius.dta", clear
xtset zip_code year
keep if inrange(year, 2014, 2023)

* generate variables (r=5km outcomes to match Table 1)
prep_vars

* encode county for FE
encode county_code, gen(county_code_fe)
gen str15 county_year_str = string(county_code_fe) + "_" + string(year)
encode county_year_str, gen(county_year_fe)

* create 3-year lagged variable
sort zip_code year
by zip_code: gen log_count_bev_lag3 = log_count_bev[_n-3]
label variable log_count_bev_lag3 "Log BEV count (t-3)"

eststo clear

* === (1) Peak r5: 2WFE ===
reghdfe log_weekday_peak_speed_r5 log_count_bev_lag3 $controls, ///
        absorb(zip_code year) vce(cluster zip_code)
eststo lag_reg1
preserve
keep if e(sample)
bysort zip_code: keep if _n == 1
count
estadd scalar N_zips = r(N)
restore
estadd local county_year_fe = "No"
estadd local year_fe = "Yes"
estadd local zip_fe = "Yes"
estadd local control = "Yes"
estadd scalar adjr2 = e(r2_a)

* === (2) Peak r5: County-Year FE ===
reghdfe log_weekday_peak_speed_r5 log_count_bev_lag3 $controls, ///
        absorb(county_year_fe) vce(cluster zip_code)
eststo lag_reg2
preserve
keep if e(sample)
bysort zip_code: keep if _n == 1
count
estadd scalar N_zips = r(N)
restore
estadd local county_year_fe = "Yes"
estadd local year_fe = "No"
estadd local zip_fe = "No"
estadd local control = "Yes"
estadd scalar adjr2 = e(r2_a)

* === (3) Midnight r5: 2WFE ===
reghdfe log_weekday_mn_speed_r5 log_count_bev_lag3 $controls, ///
        absorb(zip_code year) vce(cluster zip_code)
eststo lag_reg3
preserve
keep if e(sample)
bysort zip_code: keep if _n == 1
count
estadd scalar N_zips = r(N)
restore
estadd local county_year_fe = "No"
estadd local year_fe = "Yes"
estadd local zip_fe = "Yes"
estadd local control = "Yes"
estadd scalar adjr2 = e(r2_a)

* === (4) Midnight r5: County-Year FE ===
reghdfe log_weekday_mn_speed_r5 log_count_bev_lag3 $controls, ///
        absorb(county_year_fe) vce(cluster zip_code)
eststo lag_reg4
preserve
keep if e(sample)
bysort zip_code: keep if _n == 1
count
estadd scalar N_zips = r(N)
restore
estadd local county_year_fe = "Yes"
estadd local year_fe = "No"
estadd local zip_fe = "No"
estadd local control = "Yes"
estadd scalar adjr2 = e(r2_a)

* Export 3-year lagged results table
esttab lag_reg1 lag_reg2 lag_reg3 lag_reg4 using "$TABLES/twfe_speed_regs_lag.tex", ///
        keep(log_count_bev_lag3) coeflabel(log_count_bev_lag3 "Log BEV count \((t-3)\)") ///
        b(%9.4f) se(%9.4f) star(* 0.10 ** 0.05 *** 0.01) ///
        tex label replace ///
        stats(year_fe zip_fe county_year_fe control adjr2 N N_zips, ///
                  labels("Year fixed effects" "ZIP fixed effects" "County-year fixed effects" ///
                         "Controls" "Adjusted \(R^2\)" "Observations" "ZIP clusters") ///
                  fmt(0 0 0 0 3 0 0)) ///
        nonotes addnotes("\scriptsize \makecell[l]{Note: \sym{*} \(p<0.1\), \sym{**} \(p<0.05\), \sym{***} \(p<0.01\). \\Standard errors in parentheses are clustered at the ZIP level.\\Outcomes are speed averages within \(r=5\)km of the ZIP centroid.\\BEV count is lagged by 3 years.}") ///
        nomtitle collabels(none) ///
        mgroups("Log peak-hour speed" "Log midnight speed", ///
                pattern(1 0 1 0) ///
                prefix(\multicolumn{@span}{c}{) suffix(}) span)
