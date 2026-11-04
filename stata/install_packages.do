**************************************************
* install_packages.do -- install the user-written packages used by the
* do-files (run once).
*
* ftools, reghdfe and ivreghdfe are pinned to the versions used for the
* paper, from their GitHub release tags: SSC always serves the newest
* version, which changes over time.
*   ftools 2.49.1 (08aug2023), reghdfe 6.12.5 (27Dec2023), ivreghdfe 1.1.3 (04Jan2023)
* ivreg2, ranktest, estout and coefplot come from SSC.
**************************************************
local gh "https://raw.githubusercontent.com/sergiocorreia"

net install ftools,    from("`gh'/ftools/2.49.1/src/")    replace
net install reghdfe,   from("`gh'/reghdfe/6.12.5/src/")   replace
net install ivreghdfe, from("`gh'/ivreghdfe/1.1.3/src/")  replace

foreach p in ivreg2 ranktest estout coefplot {
    ssc install `p', replace
}

* compile ftools' Mata library
ftools, compile
