**************************************************
* _setup.do -- paths, packages, globals and helper programs
*
* Called by 00_master.do, and by each numbered do-file when it is run on its
* own. Must be run with the working directory set to stata/.
*
* Paths come from ../.env (see .env.example); a variable set in the process
* environment (e.g. by run_all.py) overrides the file. Relative paths are
* resolved against the repository root. Defines:
*   $ROOT          repository root
*   $INPUT         third-party inputs           (INPUT_DIR, default data/input)
*   $INTERMEDIATE  ZIP-year CSVs and .dta files (INTERMEDIATE_DIR, default data/intermediate)
*   $OUTPUT        generated outputs            (OUTPUT_DIR, default output)
*   $TABLES        regression tables (.tex)     ($OUTPUT/tables)
*   $FIGURES       figures (.pdf)               ($OUTPUT/figures)
*   $SEED, $N_PERM permutation-test settings    (default 20260704, 1000)
*   $controls      control variables used in every regression
**************************************************
clear all
set more off
set maxvar 10000
version 17

* --- repository root and .env ---------------------------------------------
quietly cd ..
global ROOT "`c(pwd)'"
quietly cd stata

capture confirm file "$ROOT/.env"
if !_rc {
    tempname fh
    file open `fh' using "$ROOT/.env", read text
    file read `fh' line
    while r(eof) == 0 {
        local line = strtrim(`"`macval(line)'"')
        * macval(): lines may contain ` or ', which Stata would read as macro quotes
        local eq = strpos(`"`macval(line)'"', "=")
        if substr(`"`macval(line)'"', 1, 1) != "#" & `eq' > 1 {
            local key = strtrim(substr(`"`macval(line)'"', 1, `eq' - 1))
            local val = strtrim(substr(`"`macval(line)'"', `eq' + 1, .))
            local val : subinstr local val `"""' "", all
            local val : subinstr local val "'" "", all
            local dotenv_`key' `"`macval(val)'"'
        }
        file read `fh' line
    }
    file close `fh'
}

* setting(KEY, default): process environment > .env > default
capture program drop _evc_setting
program define _evc_setting, rclass
    args key default
    local v : env `key'
    if `"`v'"' == "" local v `"${DOTENV_`key'}"'
    if `"`v'"' == "" local v `"`default'"'
    * resolve ~ and relative paths
    if substr(`"`v'"', 1, 1) == "~" {
        local home : env HOME
        local v = `"`home'"' + substr(`"`v'"', 2, .)
    }
    return local value `"`v'"'
end

foreach k in DATA_DIR INPUT_DIR INTERMEDIATE_DIR OUTPUT_DIR SEED N_PERM {
    global DOTENV_`k' `"`dotenv_`k''"'
}

_evc_setting DATA_DIR "data"
local data `"`r(value)'"'
_evc_setting INPUT_DIR "`data'/input"
global INPUT `"`r(value)'"'
_evc_setting INTERMEDIATE_DIR "`data'/intermediate"
global INTERMEDIATE `"`r(value)'"'
_evc_setting OUTPUT_DIR "output"
global OUTPUT `"`r(value)'"'
_evc_setting SEED "20260704"
global SEED `r(value)'
_evc_setting N_PERM "1000"
global N_PERM `r(value)'

foreach g in INPUT INTERMEDIATE OUTPUT {
    if substr(`"${`g'}"', 1, 1) != "/" & substr(`"${`g'}"', 2, 1) != ":" {
        global `g' `"$ROOT/${`g'}"'
    }
}
capture mkdir "$OUTPUT"
global TABLES  "$OUTPUT/tables"
global FIGURES "$OUTPUT/figures"
capture mkdir "$TABLES"
capture mkdir "$FIGURES"

display as text "ROOT         = $ROOT"
display as text "INPUT        = $INPUT"
display as text "INTERMEDIATE = $INTERMEDIATE"
display as text "OUTPUT       = $OUTPUT"
display as text "SEED / N_PERM = $SEED / $N_PERM"

* --- packages (install once with: do install_packages.do) ----------------
foreach p in reghdfe ftools ivreghdfe ivreg2 ranktest esttab coefplot {
    capture which `p'
    if _rc {
        display as error "Package `p' not found. Run: do install_packages.do"
        exit 199
    }
}

* --- controls used in every regression -------------------------------------
global controls hh_median_income population pop_density pct_pt pct_commute_45 dc_charger_pc evcs_pc pct_bachelor

* --- helper programs -----------------------------------------------------
* nzips_add: store the number of ZIPs in e(sample) as e(N_zips)
capture program drop nzips_add
program define nzips_add
    qui tab zip_code if e(sample)
    estadd scalar N_zips = r(r)
end

* prep_vars: derived controls and log treatment/outcomes shared by all
* analysis datasets
*   pop_density     residents per km^2
*   pct_bachelor    bachelor's degree holders / population
*   pct_pt          share of workers commuting by public transit
*   pct_commute_45  share of commuters travelling 45+ minutes
*   dc_charger_pc   DC fast ports per 1,000 residents (0 if none)
*   evcs_pc         all charging ports per 1,000 residents (0 if none)
*   log_count_bev   log registered BEVs (treatment)
*   log_weekday_{peak,mn}_speed_r5  log mean speed within 5 km (outcome/placebo),
*                   created only where the r=5km variables exist
capture program drop prep_vars
program define prep_vars
    gen pop_density    = population / land_area * 1000000
    gen pct_bachelor   = bachelor_degree_population / population
    gen pct_pt         = public_transport_commute / total_commute
    gen pct_commute_45 = (travel_time_45_59 + travel_time_60_89 + travel_time_90_plus) / total_travel_time
    gen dc_charger_pc  = dc_count / population * 1000
    replace dc_charger_pc = 0 if missing(dc_charger_pc)
    gen evcs_pc        = total_count / population * 1000
    replace evcs_pc = 0 if missing(evcs_pc)
    gen log_count_bev  = log(count_batteryelectricbev)
    cap gen log_weekday_peak_speed_r5 = log(weekday_peak_weighted_speed_r5)
    cap gen log_weekday_mn_speed_r5   = log(weekday_mn_weighted_speed_r5)
end

global EVC_SETUP 1
