**************************************************
* 02_main_tables.do -- Table 1 (speed: OLS, county-year FE, 2SLS) and Table 2 (mechanisms).
* Outputs: twfe_speed_regs.tex, twfe_mechanism_regs.tex
* Run via 00_master.do (or run_all.py); standalone runs load _setup.do.
**************************************************
if "$EVC_SETUP" == "" do "_setup.do"

**************************************************
* 2. Import the merged dataset and prepare for analysis
**************************************************
* Import the merged dataset
use "$INTERMEDIATE/maindata.dta", clear // load merged main dataset
xtset zip_code year // declare panel structure

* Generate variables for analysis
//calculate total number of vehicles
gen count_total = count_batteryelectricbev / proportion_batteryelectricbev
label variable count_total "Total Vehicle"
//create COVID-19 dummy (1 if 2020 <= year <= 2022)
gen covid = (year >= 2020 & year <= 2022)
label variable covid "COVID-19 Period Dummy"
//encode county_code for fe
encode county_code, gen(county_code_fe)
//generate county-year fixed effects
gen str15 county_year_str = string(county_code_fe) + "_" + string(year)
encode county_year_str, gen(county_year_fe)
//encode county_sub_code for fe
encode county_sub_code, gen(county_sub_code_fe)
//generate county sub-year fixed effects
gen str15 county_sub_year_str = string(county_sub_code_fe) + "_" + string(year)
encode county_sub_year_str, gen(county_sub_year_fe)
label variable county_year_fe "County-Year FE"
//derived controls + log BEV count (shared helper)
prep_vars

* Log transformations of variables used in the analysis
gen log_count_total = log(count_total)
label variable log_count_total "Log Total Vehicle Count"
label variable log_count_bev "Log BEV Count"
gen log_count_non_bev = log(count_total - count_batteryelectricbev)
label variable log_count_non_bev "Log Non-BEV Count"
gen log_count_gasoline = log(count_gasoline)
label variable log_count_gasoline "Log Gasoline Vehicle Count"
gen log_share_bev = log(proportion_batteryelectricbev)
label variable log_share_bev "Log BEV Proportion"
gen log_weekday_peak_speed = log(weekday_peak_weighted_speed)
label variable log_weekday_peak_speed "Log Weekday Peak-hour Speed"
gen log_n_weekday_peak_speed = log(normal_weekday_peak_weighted_)
label variable log_n_weekday_peak_speed "Log Normal Weekday Peak-hour Speed"
gen log_weekend_mid_night_speed = log(weekend_mid_night_weighted_speed)
label variable log_weekend_mid_night_speed "Log Weekend Midnight Speed"
gen log_weekend_all_speed = log(weekend_all_day_weighted_speed)
label variable log_weekend_all_speed "Log Weekend All Speed"
gen log_weekday_mid_night_speed = log(weekday_mid_night_weighted_speed)
label variable log_weekday_mid_night_speed "Log Weekday Midnight Speed"

gen log_weekday_avg_hourly_flow = log(weekday_all_day_avg_hourly_flow)
label variable log_weekday_avg_hourly_flow "Log Weekday Hourly Flow"
gen log_n_weekday_avg_hourly_flow = log(normal_weekday_all_day_avg_hourl)
label variable log_n_weekday_avg_hourly_flow "Log Normal Weekday Hourly Flow"
gen log_weekday_avg_mid_night_flow = log(weekday_mid_night_avg_hourly_flo)
label variable log_weekday_avg_mid_night_flow "Log Weekday Midnight Hourly Flow"

* proportion to percentage
gen pct_bev = proportion_batteryelectricbev * 100
gen pct_non_bev = (1 - proportion_batteryelectricbev) * 100
gen log_pct_bev = log(pct_bev)
gen log_pct_non_bev = log(pct_non_bev)

* Describe panel and variables
xtdescribe
describe
summarize


**************************************************
* 3. MAIN REGRESSION ANALYSIS
**************************************************
keep if inrange(year, 2014, 2023) // keep data from 2014-2023, our study period

**************************************************
* 3.1. Main regression on traffic speed (Table 1)
*      Outcomes at r=5km: weekday peak (cols 1-3), weekday midnight (cols 4-6)
*      Col 1/4: OLS 2WFE | Col 2/5: OLS CY-FE | Col 3/6: 2SLS 2WFE
**************************************************
preserve
use "$INTERMEDIATE/maindata_r5_iv.dta", clear
xtset zip_code year
keep if inrange(year, 2014, 2023)
prep_vars

eststo clear

* === (1) Peak r5: OLS 2WFE ===
reghdfe log_weekday_peak_speed_r5 log_count_bev $controls, ///
    absorb(zip_code year) vce(cluster zip_code)
estadd local kpf ""
estadd scalar adjr2 = e(r2_a)
nzips_add
estadd local zip_fe    "Yes"
estadd local year_fe   "Yes"
estadd local cy_fe     "No"
estadd local control   "Yes"
estadd local iv "No"
eststo reg1

* === (2) Peak r5: 2SLS 2WFE ===
ivreghdfe log_weekday_peak_speed_r5 (log_count_bev = z_cap_100) $controls, ///
    absorb(zip_code year) cluster(zip_code) first
estadd scalar kpf = e(widstat)
nzips_add
estadd local zip_fe    "Yes"
estadd local year_fe   "Yes"
estadd local cy_fe     "No"
estadd local control   "Yes"
estadd local iv "Yes"
eststo reg2

* === (3) Peak r5: OLS CY-FE ===
reghdfe log_weekday_peak_speed_r5 log_count_bev $controls, ///
    absorb(county_year_fe) vce(cluster zip_code)
estadd local kpf ""
estadd scalar adjr2 = e(r2_a)
nzips_add
estadd local zip_fe    "No"
estadd local year_fe   "No"
estadd local cy_fe     "Yes"
estadd local control   "Yes"
estadd local iv "No"
eststo reg3

* === (4) Midnight r5: OLS 2WFE ===
reghdfe log_weekday_mn_speed_r5 log_count_bev $controls, ///
    absorb(zip_code year) vce(cluster zip_code)
estadd local kpf ""
estadd scalar adjr2 = e(r2_a)
nzips_add
estadd local zip_fe    "Yes"
estadd local year_fe   "Yes"
estadd local cy_fe     "No"
estadd local control   "Yes"
estadd local iv "No"
eststo reg4

* === (5) Midnight r5: 2SLS 2WFE ===
ivreghdfe log_weekday_mn_speed_r5 (log_count_bev = z_cap_100) $controls, ///
    absorb(zip_code year) cluster(zip_code) first
estadd scalar kpf = e(widstat)
nzips_add
estadd local zip_fe    "Yes"
estadd local year_fe   "Yes"
estadd local cy_fe     "No"
estadd local control   "Yes"
estadd local iv "Yes"
eststo reg5

* === (6) Midnight r5: OLS CY-FE ===
reghdfe log_weekday_mn_speed_r5 log_count_bev $controls, ///
    absorb(county_year_fe) vce(cluster zip_code)
estadd local kpf ""
estadd scalar adjr2 = e(r2_a)
nzips_add
estadd local zip_fe    "No"
estadd local year_fe   "No"
estadd local cy_fe     "Yes"
estadd local control   "Yes"
estadd local iv "No"
eststo reg6

esttab reg1 reg3 reg2 reg4 reg6 reg5 using "$TABLES/twfe_speed_regs.tex", ///
    keep(log_count_bev) coeflabel(log_count_bev "Log BEV count") ///
    b(%9.4f) se(%9.4f) star(* 0.1 ** 0.05 *** 0.01) ///
    tex label replace ///
    stats(zip_fe year_fe cy_fe iv control kpf adjr2 N N_zips, ///
          labels("ZIP fixed effects" "Year fixed effects" "County-year fixed effects" "Instrumental variables" "Controls" "First stage \textit{F}" "Adjusted \(R^2\)" "Observations" "ZIP clusters") ///
          fmt(0 0 0 0 0 2 3 0 0)) ///
    nonotes addnotes("\scriptsize \makecell[l]{Note: \sym{*} \(p<0.1\), \sym{**} \(p<0.05\), \sym{***} \(p<0.01\). Robust standard errors in parentheses are clustered by the ZIP level. \\The outcome in columns (1)-(3) is the average freeway peak-hour speed within 5-km radius from the ZIP centroid. \\The outcome in columns (4)-(6) is the average freeway midnight speed within 5-km radius from the ZIP centroid. \\The BEV count is instrumented together by the income-ineligible population share and CVRP policy shock.}") ///
    nomtitle collabels(none) ///
    mgroups("Log peak-hour speed" "Log midnight speed", ///
            pattern(1 0 0 1 0 0) ///
            prefix(\multicolumn{@span}{c}{) suffix(}) span)

restore


**************************************************
* 3.2. Mechanism Analysis: Ownership, Flow, Transit
**************************************************
* (1) Ownership: 2WFE (ZIP-Year FE)
gen d_log_count_bev = d.log_count_bev
label variable d_log_count_bev "\(\Delta\) Log BEV count"

reghdfe d.log_count_total d_log_count_bev $controls, ///
        absorb(zip_code year) vce(cluster zip_code)
eststo reg1
preserve
keep if e(sample)
bysort zip_code: keep if _n == 1
count
scalar N_zips_reg1 = r(N)
restore
estadd local county_year_fe = "No"
estadd local year_fe = "Yes"
estadd local zip_fe = "Yes"
estadd local ua_fe = "No"
estadd scalar N_units = N_zips_reg1
estadd local control = "Yes"
estadd scalar adjr2 = e(r2_a)

* (2) Ownership: County-Year FE
reghdfe d.log_count_total d_log_count_bev $controls, ///
        absorb(county_year_fe) vce(cluster zip_code)
eststo reg2
preserve
keep if e(sample)
bysort zip_code: keep if _n == 1
count
scalar N_zips_reg2 = r(N)
restore
estadd local county_year_fe = "Yes"
estadd local year_fe = "No"
estadd local zip_fe = "No"
estadd local ua_fe = "No"
estadd scalar N_units = N_zips_reg2
estadd local control = "Yes"
estadd scalar adjr2 = e(r2_a)

* (3) Flow: 2WFE (ZIP-Year FE)
reghdfe log_weekday_avg_hourly_flow log_count_bev $controls, ///
        absorb(zip_code year) vce(cluster zip_code)
eststo reg3
preserve
keep if e(sample)
bysort zip_code: keep if _n == 1
count
scalar N_zips_reg3 = r(N)
restore
estadd local county_year_fe = "No"
estadd local year_fe = "Yes"
estadd local zip_fe = "Yes"
estadd local ua_fe = "No"
estadd scalar N_units = N_zips_reg3
estadd local control = "Yes"
estadd scalar adjr2 = e(r2_a)

* (4) Flow: County-Year FE
reghdfe log_weekday_avg_hourly_flow log_count_bev $controls, ///
        absorb(county_year_fe) vce(cluster zip_code)
eststo reg4
preserve
keep if e(sample)
bysort zip_code: keep if _n == 1
count
scalar N_zips_reg4 = r(N)
restore
estadd local county_year_fe = "Yes"
estadd local year_fe = "No"
estadd local zip_fe = "No"
estadd local ua_fe = "No"
estadd scalar N_units = N_zips_reg4
estadd local control = "Yes"
estadd scalar adjr2 = e(r2_a)

* (5) Public Transit: 2WFE (UA-Year FE)
preserve
use "$INTERMEDIATE/uantddata.dta", clear
keep if inrange(year, 2014, 2023) // align with ZIP study period
xtset ua year

reghdfe log_pt_ridership log_count_bev $controls, ///
        absorb(ua year) vce(cluster ua)
eststo reg5

* Count unique UAs in the regression sample
keep if e(sample)
bysort ua: keep if _n == 1
count
scalar N_uas_reg5 = r(N)

* Save the estadd locals and scalars while still in the preserved dataset
estadd local county_year_fe = "No"
estadd local year_fe = "Yes"
estadd local zip_fe = "No"
estadd local ua_fe = "Yes"
estadd scalar N_units = N_uas_reg5
estadd local control = "Yes"
estadd scalar adjr2 = e(r2_a)
restore

* Export Mechanism Table
esttab reg1 reg2 reg3 reg4 reg5 using "$TABLES/twfe_mechanism_regs.tex", ///
    keep(d_log_count_bev log_count_bev) ///
    coeflabel(d_log_count_bev "Log \(\Delta\)BEV count" log_count_bev "Log BEV count") ///
    b(%9.4f) se(%9.4f) star(* 0.1 ** 0.05 *** 0.01) ///
    tex label replace ///
    stats(year_fe zip_fe ua_fe county_year_fe control adjr2 N N_units, ///
          labels("Year fixed effects" "ZIP fixed effects" "UA fixed effects" "County-Year fixed effects" ///
                 "Controls" "Adjusted \(R^2\)" "Observations" "Unit clusters") ///
          fmt(0 0 0 0 0 3 0 0)) ///
    nonotes addnotes("\scriptsize \makecell[l]{Note: \sym{*} \(p<0.1\), \sym{**} \(p<0.05\), \sym{***} \(p<0.01\). UA = Urbanized area, PT = Public transit. \\Standard errors in parentheses are clustered at ZIP level in columns (1)-(4) and UA level in column (5). \\Outcomes in columns (1)-(4) are measured at the ZIP level, and column (5) is measured at the UA level.}") ///
    nomtitle collabels(none) ///
    mgroups(" Log \(\Delta\)vehicle ownership" "Log hourly flow" "Log PT ridership", ///
            pattern(1 0 1 0 1) ///
            prefix(\multicolumn{@span}{c}{) suffix(}) span erepeat(\cmidrule(lr){@span}))
