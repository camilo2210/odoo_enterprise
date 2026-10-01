{
  "version": "19.3.10",
  "sheets": [
    {
      "id": "dashboard_sheet_id",
      "name": "Dashboard",
      "colNumber": 10,
      "rowNumber": 22,
      "rows": {
        "21": { "size": 9 }
      },
      "cols": {
        "0": { "size": 136 }
      },
      "merges": [],
      "cells": {},
      "styles": {},
      "formats": {},
      "borders": {},
      "conditionalFormats": [],
      "dataValidationRules": [],
      "figures": [
        {
          "id": "b82b24e3-b4bb",
          "col": 0,
          "row": 0,
          "offset": { "x": 0, "y": 10 },
          "width": 242,
          "height": 117,
          "tag": "chart",
          "data": {
            "type": "scorecard",
            "keyValue": "Data!D2",
            "title": { "text": "FTE", "color": "#01666B", "bold": true },
            "baselineMode": "percentage",
            "baselineColorUp": "#43C5B1",
            "baselineColorDown": "#EA6175",
            "humanize": true,
            "baseline": "Data!E2",
            "chartId": "9d32716e-3182"
          }
        },
        {
          "id": "d5d18c0e-6a41",
          "col": 4,
          "row": 0,
          "offset": { "x": 81, "y": 10 },
          "width": 242,
          "height": 117,
          "tag": "chart",
          "data": {
            "type": "scorecard",
            "keyValue": "Data!D4",
            "title": { "text": "Open Appraisals", "color": "#01666B", "bold": true },
            "baselineMode": "percentage",
            "baselineColorUp": "#43C5B1",
            "baselineColorDown": "#EA6175",
            "humanize": true,
            "baseline": "Data!E4",
            "chartId": "75952a4a-cf61"
          }
        },
        {
          "id": "b9036c8b-0f61",
          "col": 7,
          "row": 0,
          "offset": { "x": 46, "y": 10 },
          "width": 242,
          "height": 117,
          "tag": "chart",
          "data": {
            "type": "scorecard",
            "keyValue": "Data!D7",
            "title": { "text": "Turnover Rate", "color": "#01666B", "bold": true },
            "baselineMode": "percentage",
            "baselineColorUp": "#43C5B1",
            "baselineColorDown": "#EA6175",
            "humanize": true,
            "baseline": "Data!E7",
            "chartId": "774beba8-47e6"
          }
        },
        {
          "id": "606dec32-0200",
          "col": 2,
          "row": 0,
          "offset": { "x": 21, "y": 10 },
          "width": 242,
          "height": 117,
          "tag": "chart",
          "data": {
            "type": "scorecard",
            "keyValue": "Data!D3",
            "title": { "text": "Departments", "bold": true, "color": "#01666B" },
            "baselineMode": "percentage",
            "baselineColorUp": "#43C5B1",
            "baselineColorDown": "#EA6175",
            "baseline": "Data!E3",
            "humanize": true,
            "chartId": "a8698c58-30e9"
          }
        },
        {
          "id": "e4359f64-5099",
          "col": 0,
          "row": 0,
          "offset": { "x": 0, "y": 137 },
          "width": 495,
          "height": 335,
          "tag": "carousel",
          "data": {
            "chartDefinitions": {
              "c9ecb2fa-ba4f": {
                "dataSource": {
                  "labelRange": "'Employee Pyramid'!A:A",
                  "type": "range",
                  "dataSets": [
                    { "dataSetId": "0", "dataRange": "'Employee Pyramid'!B:B" },
                    { "dataSetId": "1", "dataRange": "'Employee Pyramid'!C:C" }
                  ],
                  "dataSetsHaveTitle": true
                },
                "dataSetStyles": {
                  "0": { "backgroundColor": "#4EA7F2" },
                  "1": { "backgroundColor": "#EA6175" }
                },
                "aggregated": false,
                "legendPosition": "top",
                "title": {},
                "type": "pyramid",
                "horizontal": true,
                "stacked": true,
                "humanize": true
              }
            },
            "title": {
              "bold": true,
              "fontSize": 21,
              "color": "#01666B",
              "text": "Employee Pyramid"
            },
            "items": [
              { "type": "chart", "chartId": "c9ecb2fa-ba4f" }
            ],
            "fieldMatching": {}
          }
        },
        {
          "id": "c9495200-3048",
          "col": 0,
          "row": 0,
          "offset": { "x": 505, "y": 137 },
          "width": 495,
          "height": 335,
          "tag": "carousel",
          "data": {
            "chartDefinitions": {
              "c17ddd3e-1e29": {
                "dataSource": {
                  "labelRange": "'Appraisals by Final Rating'!A:A",
                  "type": "range",
                  "dataSets": [
                    { "dataSetId": "0", "dataRange": "'Appraisals by Final Rating'!B:B" }
                  ],
                  "dataSetsHaveTitle": true
                },
                "dataSetStyles": {},
                "legendPosition": "top",
                "title": {},
                "type": "pie",
                "aggregated": false,
                "isDoughnut": false,
                "humanize": true
              }
            },
            "title": {
              "italic": false,
              "bold": true,
              "fontSize": 21,
              "color": "#01666B",
              "text": "Appraisal Final Rating"
            },
            "items": [
              { "type": "chart", "chartId": "c17ddd3e-1e29" }
            ],
            "fieldMatching": {}
          }
        }
      ],
      "tables": [],
      "areGridLinesVisible": true,
      "isVisible": true,
      "backgroundColor": "#F9FAFB",
      "headerGroups": {
        "ROW": [],
        "COL": []
      },
      "comments": {}
    },
    {
      "id": "bf1b3909-b703",
      "name": "Data",
      "colNumber": 26,
      "rowNumber": 102,
      "rows": {},
      "cols": {
        "0": { "size": 121 }
      },
      "merges": [],
      "cells": {
        "A2": "FTE",
        "A3": "Departments",
        "A4": "Open Appraisals",
        "A5": "New Employees",
        "A6": "Leaving Employees",
        "A7": "Turnover Rate",
        "B1": "Current",
        "B2": "=PIVOT.VALUE(1,\"__count:sum\")",
        "B3": {
          "N": "+1",
          "S": ["__count:count"]
        },
        "B4:B5": {
          "N": "+2",
          "S": ["="]
        },
        "B6": {
          "N": "+1",
          "S": ["="]
        },
        "B7": "=(B6+B5)/2/B2",
        "C1": "Previous",
        "C2": "=PIVOT.VALUE(10,\"__count:sum\")",
        "C3": {
          "N": "+-7",
          "S": ["__count:count"]
        },
        "C4": {
          "N": "+2",
          "S": ["="]
        },
        "C5": {
          "N": "+3",
          "S": ["="]
        },
        "C6": {
          "N": "+1",
          "S": ["="]
        },
        "C7": "=(C6+C5)/2/C2",
        "D1": "Current",
        "D2": "=FORMAT.LARGE.NUMBER(B2)",
        "D3:D4": { "R": "+R1" },
        "D7": { "R": "+R3" },
        "E1": "Previous",
        "E2": "=FORMAT.LARGE.NUMBER(C2)",
        "E3:E4": { "R": "+R1" },
        "E7": { "R": "+R3" }
      },
      "styles": { "A2:A7": 1, "D1:E1": 1 },
      "formats": { "B7:C7": 1 },
      "borders": { "C2": 1 },
      "conditionalFormats": [],
      "dataValidationRules": [],
      "figures": [],
      "tables": [],
      "areGridLinesVisible": true,
      "isVisible": true,
      "isLocked": false,
      "headerGroups": {
        "ROW": [],
        "COL": []
      },
      "comments": {}
    },
    {
      "id": "e7947a3e-9864",
      "name": "Employee Pyramid",
      "colNumber": 26,
      "rowNumber": 100,
      "rows": {},
      "cols": {
        "6": { "size": 105 },
        "8": { "size": 77 },
        "9": { "size": 31 }
      },
      "merges": [],
      "cells": { "A1": "=PIVOT(11,,false,,,false)", "G1": "=ODOO.LIST(1,80)" },
      "styles": {},
      "formats": {},
      "borders": {},
      "conditionalFormats": [],
      "dataValidationRules": [],
      "figures": [],
      "tables": [
        {
          "range": "G1",
          "type": "dynamic",
          "config": {
            "hasFilters": false,
            "totalRow": false,
            "firstColumn": false,
            "lastColumn": false,
            "numberOfHeaders": 1,
            "bandedRows": true,
            "bandedColumns": false,
            "styleId": "TableStyleMedium5",
            "automaticAutofill": false
          }
        }
      ],
      "areGridLinesVisible": true,
      "isVisible": true,
      "isLocked": false,
      "headerGroups": {
        "ROW": [],
        "COL": []
      },
      "comments": {}
    },
    {
      "id": "b0c4fd92-3d07",
      "name": "Appraisals by Final Rating",
      "colNumber": 26,
      "rowNumber": 100,
      "rows": {},
      "cols": {
        "0": { "size": 200 }
      },
      "merges": [],
      "cells": { "A1": "=PIVOT(13,,FALSE,false,,)" },
      "styles": {},
      "formats": {},
      "borders": {},
      "conditionalFormats": [],
      "dataValidationRules": [],
      "figures": [],
      "tables": [],
      "areGridLinesVisible": true,
      "isVisible": true,
      "isLocked": false,
      "headerGroups": {
        "ROW": [],
        "COL": []
      },
      "comments": {}
    }
  ],
  "styles": {
    "1": { "bold": true }
  },
  "formats": { "1": "0.00%" },
  "borders": {
    "1": {
      "top": { "color": "#4F3448", "style": "thin" },
      "bottom": { "color": "#4F3448", "style": "medium" }
    }
  },
  "revisionId": "START_REVISION",
  "uniqueFigureIds": true,
  "settings": {
    "locale": {
      "name": "English (US)",
      "code": "en_US",
      "thousandsSeparator": ",",
      "decimalSeparator": ".",
      "dateFormat": "mm/dd/yyyy",
      "timeFormat": "hh:mm:ss a",
      "formulaArgSeparator": ",",
      "weekStart": 7,
      "digitGrouping": "[3,0]"
    }
  },
  "pivots": {
    "4fc3d020-8587": {
      "type": "ODOO",
      "name": "Employee",
      "model": "hr.employee",
      "rows": [],
      "columns": [],
      "measures": [
        { "id": "__count:sum", "fieldName": "__count", "aggregator": "sum" }
      ],
      "style": { "tableStyleId": "PivotTableStyleMedium12" },
      "filters": [],
      "formulaId": "1",
      "domain": [],
      "fieldMatching": {
        "ae105232-a3bf": { "chain": "contract_date_start", "type": "date", "offset": 0 },
        "84866d00-957c": { "chain": "employee_id", "type": "many2one" },
        "966c306b-0a87": { "chain": "department_id", "type": "many2one" }
      }
    },
    "8d967d71-14f6": {
      "type": "ODOO",
      "name": "Department",
      "model": "hr.department",
      "rows": [],
      "columns": [],
      "measures": [
        { "id": "__count:count", "fieldName": "__count", "aggregator": "count" }
      ],
      "style": { "tableStyleId": "PivotTableStyleMedium12" },
      "formulaId": "2",
      "domain": [],
      "fieldMatching": {
        "ae105232-a3bf": { "chain": "create_date", "type": "datetime", "offset": 0 },
        "84866d00-957c": { "chain": "manager_id.employee_id", "type": "many2one" },
        "966c306b-0a87": { "chain": "id", "type": "integer" }
      }
    },
    "df660165-fb92": {
      "type": "ODOO",
      "name": "Department (copy)",
      "model": "hr.department",
      "rows": [],
      "columns": [],
      "measures": [
        { "id": "__count:count", "fieldName": "__count", "aggregator": "count" }
      ],
      "style": { "tableStyleId": "PivotTableStyleMedium12" },
      "formulaId": "3",
      "domain": [],
      "fieldMatching": {
        "ae105232-a3bf": { "chain": "create_date", "type": "datetime", "offset": -1 },
        "84866d00-957c": { "chain": "manager_id.employee_id", "type": "many2one" },
        "966c306b-0a87": { "chain": "id", "type": "integer" }
      }
    },
    "371a08c9-6713": {
      "type": "ODOO",
      "name": "Employee Appraisal",
      "model": "hr.appraisal",
      "rows": [],
      "columns": [],
      "measures": [
        { "id": "__count:count", "fieldName": "__count", "aggregator": "count" }
      ],
      "style": { "tableStyleId": "PivotTableStyleMedium12" },
      "filters": [],
      "domain": [
        ["state", "=", "2_pending"]
      ],
      "formulaId": "4",
      "fieldMatching": {
        "ae105232-a3bf": { "chain": "create_date", "type": "datetime", "offset": 0 },
        "84866d00-957c": { "chain": "employee_id", "type": "many2one" },
        "966c306b-0a87": { "chain": "department_id", "type": "many2one" }
      }
    },
    "aa606c71-427a": {
      "type": "ODOO",
      "name": "Employee Appraisal (copy)",
      "model": "hr.appraisal",
      "rows": [],
      "columns": [],
      "measures": [
        { "id": "__count:count", "fieldName": "__count", "aggregator": "count" }
      ],
      "style": { "tableStyleId": "PivotTableStyleMedium12" },
      "filters": [],
      "domain": [
        ["state", "=", "2_pending"]
      ],
      "formulaId": "5",
      "fieldMatching": {
        "ae105232-a3bf": { "chain": "create_date", "type": "datetime", "offset": -1 },
        "84866d00-957c": { "chain": "employee_id", "type": "many2one" },
        "966c306b-0a87": { "chain": "department_id", "type": "many2one" }
      }
    },
    "ee02553e-0c7f": {
      "type": "ODOO",
      "name": "Employee",
      "model": "hr.employee",
      "rows": [],
      "columns": [],
      "measures": [
        { "id": "__count:count", "fieldName": "__count", "aggregator": "count" }
      ],
      "style": { "tableStyleId": "PivotTableStyleMedium12" },
      "filters": [],
      "domain": [
        ["contract_date_end", "=", false]
      ],
      "formulaId": "6",
      "fieldMatching": {
        "ae105232-a3bf": { "chain": "contract_date_start", "type": "date" },
        "84866d00-957c": { "chain": "employee_id", "type": "many2one" },
        "966c306b-0a87": { "chain": "department_id", "type": "many2one" }
      }
    },
    "ba7543b4-386a": {
      "type": "ODOO",
      "name": "Employee (copy)",
      "model": "hr.employee",
      "rows": [],
      "columns": [],
      "measures": [
        { "id": "__count:count", "fieldName": "__count", "aggregator": "count" }
      ],
      "style": { "tableStyleId": "PivotTableStyleMedium12" },
      "filters": [],
      "domain": [
        ["contract_date_end", "!=", false]
      ],
      "formulaId": "7",
      "fieldMatching": {
        "ae105232-a3bf": { "chain": "contract_date_end", "type": "date", "offset": 0 },
        "84866d00-957c": { "chain": "employee_id", "type": "many2one" },
        "966c306b-0a87": { "chain": "department_id", "type": "many2one" }
      }
    },
    "3bea0211-5b9e": {
      "type": "ODOO",
      "name": "Employee (copy)",
      "model": "hr.employee",
      "rows": [],
      "columns": [],
      "measures": [
        { "id": "__count:count", "fieldName": "__count", "aggregator": "count" }
      ],
      "style": { "tableStyleId": "PivotTableStyleMedium12" },
      "filters": [],
      "domain": [
        ["contract_date_end", "=", false]
      ],
      "formulaId": "8",
      "fieldMatching": {
        "ae105232-a3bf": { "chain": "contract_date_start", "type": "date", "offset": -1 },
        "84866d00-957c": { "chain": "employee_id", "type": "many2one" },
        "966c306b-0a87": { "chain": "department_id", "type": "many2one" }
      }
    },
    "ae0ac4f9-d736": {
      "type": "ODOO",
      "name": "Employee (copy) (copy)",
      "model": "hr.employee",
      "rows": [],
      "columns": [],
      "measures": [
        { "id": "__count:count", "fieldName": "__count", "aggregator": "count" }
      ],
      "style": { "tableStyleId": "PivotTableStyleMedium12" },
      "filters": [],
      "domain": [
        ["contract_date_end", "!=", false]
      ],
      "formulaId": "9",
      "fieldMatching": {
        "ae105232-a3bf": { "chain": "contract_date_end", "type": "date", "offset": -1 },
        "84866d00-957c": { "chain": "employee_id", "type": "many2one" },
        "966c306b-0a87": { "chain": "department_id", "type": "many2one" }
      }
    },
    "f06aec22-3337": {
      "type": "ODOO",
      "name": "Employee (copy)",
      "model": "hr.employee",
      "rows": [],
      "columns": [],
      "measures": [
        { "id": "__count:sum", "fieldName": "__count", "aggregator": "sum" }
      ],
      "style": { "tableStyleId": "PivotTableStyleMedium12" },
      "filters": [],
      "formulaId": "10",
      "domain": [],
      "fieldMatching": {
        "ae105232-a3bf": { "chain": "contract_date_start", "type": "date", "offset": -1 },
        "84866d00-957c": { "chain": "employee_id", "type": "many2one" },
        "966c306b-0a87": { "chain": "department_id", "type": "many2one" }
      }
    },
    "c53b1252-bee9": {
      "dataSet": {
        "sheetId": "e7947a3e-9864",
        "zone": { "right": 10, "top": 0, "left": 6, "bottom": 99 }
      },
      "columns": [
        { "fieldName": "Sex", "order": "asc" }
      ],
      "rows": [
        { "fieldName": "Age Levels", "order": "asc" }
      ],
      "measures": [
        { "id": "__count:sum", "fieldName": "__count", "aggregator": "sum" }
      ],
      "filters": [],
      "name": "New pivot",
      "type": "SPREADSHEET",
      "style": { "tableStyleId": "PivotTableStyleMedium12" },
      "formulaId": "11"
    },
    "ea947567-3b3a": {
      "type": "ODOO",
      "name": "Appraisals by Final Rating",
      "model": "hr.appraisal",
      "domain": [],
      "context": {},
      "rows": [
        { "fieldName": "assessment_note" }
      ],
      "columns": [],
      "measures": [
        { "id": "__count", "fieldName": "__count" }
      ],
      "actionXmlId": "hr_appraisal.open_view_hr_appraisal_tree",
      "style": { "tableStyleId": "PivotTableStyleMedium12" },
      "formulaId": "12",
      "fieldMatching": {
        "ae105232-a3bf": { "chain": "create_date", "type": "datetime" },
        "84866d00-957c": { "chain": "employee_id", "type": "many2one" },
        "966c306b-0a87": { "chain": "department_id", "type": "many2one" }
      }
    },
    "e7de8676-4bec": {
      "type": "ODOO",
      "name": "Appraisal Final Rating",
      "model": "hr.appraisal",
      "domain": [],
      "context": {},
      "rows": [
        { "fieldName": "assessment_note" }
      ],
      "columns": [],
      "measures": [
        { "id": "__count", "fieldName": "__count" }
      ],
      "actionXmlId": "hr_appraisal.open_view_hr_appraisal_tree",
      "style": { "tableStyleId": "PivotTableStyleMedium12" },
      "formulaId": "13",
      "fieldMatching": {
        "ae105232-a3bf": { "chain": "create_date", "type": "datetime" },
        "84866d00-957c": { "chain": "employee_id", "type": "many2one" },
        "966c306b-0a87": { "chain": "department_id", "type": "many2one" }
      }
    }
  },
  "pivotNextId": 14,
  "customTableStyles": {},
  "namedRanges": {},
  "globalFilters": [
    { "id": "ae105232-a3bf", "label": "Date", "type": "date" },
    {
      "id": "84866d00-957c",
      "label": "Employee",
      "type": "relation",
      "modelName": "hr.employee",
      "domainOfAllowedValues": []
    },
    {
      "id": "966c306b-0a87",
      "label": "Department",
      "type": "relation",
      "modelName": "hr.department",
      "domainOfAllowedValues": []
    }
  ],
  "lists": {
    "1": {
      "model": "hr.employee",
      "name": "Employee",
      "columns": [
        { "name": "name", "string": "Name" },
        { "name": "sex", "string": "Sex", "hidden": false },
        { "name": "birthday", "string": "Birthday", "hidden": false },
        {
          "name": "Age",
          "string": "Age",
          "computedBy": {
            "sheetId": "31702e0e-9c3a",
            "formula": "=DATEDIF(birthday,today(),\"Y\")"
          },
          "hidden": false
        },
        {
          "name": "Age Levels",
          "string": "Age Levels",
          "computedBy": {
            "sheetId": "31702e0e-9c3a",
            "formula": "=FLOOR(Age,5) & \"-\" & (FLOOR(Age,5)+4)"
          },
          "hidden": false
        }
      ],
      "domain": [],
      "context": {},
      "orderBy": [],
      "fieldMatching": {
        "ae105232-a3bf": { "chain": "contract_date_start", "type": "date" },
        "84866d00-957c": { "chain": "employee_id", "type": "many2one" },
        "966c306b-0a87": { "chain": "department_id", "type": "many2one" }
      },
      "translateHeaders": true
    }
  },
  "listNextId": 2,
  "odooLinkReferences": {
    "a8698c58-30e9": {
      "type": "dataSource",
      "dataSourceType": "pivot",
      "dataSourceCoreId": "8d967d71-14f6"
    },
    "c17ddd3e-1e29": {
      "type": "dataSource",
      "dataSourceType": "pivot",
      "dataSourceCoreId": "e7de8676-4bec"
    },
    "c9ecb2fa-ba4f": { "type": "odooMenu", "odooMenuId": "hr.menu_hr_root" }
  }
}
