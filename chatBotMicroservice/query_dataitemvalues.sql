-- Query to find all distinct dataItemValue entries in the financials_dt table
-- This will help identify the exact column names available for filtering

SELECT DISTINCT dataItemValue
FROM `cbldt-b016-int-2e05.dw_ext_sgam_1832_sp_ist.financials_dt`
WHERE dataItemValue IS NOT NULL
ORDER BY dataItemValue;

-- Query to find dataItemValue entries related to "Net Income" for Apple
SELECT DISTINCT dataItemValue
FROM `cbldt-b016-int-2e05.dw_ext_sgam_1832_sp_ist.financials_dt` f
LEFT JOIN `cbldt-b016-int-2e05.dw_ext_sgam_1832_sp_ist.mv_bbg_sp_trade` bbg 
  ON f.companyId = bbg.companyId
WHERE bbg.companyName LIKE '%Apple%'
  AND dataItemValue LIKE '%Net%'
ORDER BY dataItemValue;

-- Query to see sample data for Apple with various metrics
SELECT 
  f.filingDate,
  bbg.companyName,
  f.dataItemValue,
  f.collectionDataItemValue,
  f.unitTypeName
FROM `cbldt-b016-int-2e05.dw_ext_sgam_1832_sp_ist.financials_dt` f
LEFT JOIN `cbldt-b016-int-2e05.dw_ext_sgam_1832_sp_ist.mv_bbg_sp_trade` bbg 
  ON f.companyId = bbg.companyId
WHERE bbg.companyName LIKE '%Apple%'
  AND f.filingDate >= DATE_SUB(CURRENT_DATE(), INTERVAL 1 YEAR)
  AND f.periodTypeName = 'Quarterly'
  AND f.dataItemValue LIKE '%Income%'
ORDER BY f.filingDate DESC, f.dataItemValue
LIMIT 100;
