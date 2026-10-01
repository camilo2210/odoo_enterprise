{
  "header": {
    "transactionDate": "2025-10-20",
    "amountCalcType": "gross",
    "documentCode": "___ignore___",
    "messageType": "goods",
    "companyLocation": "49233848000150",
    "operationType": "standardSales",
    "payment": {
      "bill": {
        "vNet": 15.0,
        "vOrig": 15.0
      },
      "installment": [{
        "date": "___ignore___",
        "documentNumber": "001",
        "grossValue": 15.0,
        "netValue": 15.0
      }],
      "installmentTerms": "1"
    },
    "locations": {
      "entity": {
        "name": "Foreign Partner",
        "businessName": "Foreign Partner",
        "type": "foreign",
        "federalTaxId": "9999999999",
        "address": {
          "neighborhood": "EXTERIOR",
          "street": "Santa Barbara Rd",
          "number": "77",
          "zipcode": "99999999",
          "cityName": "EXTERIOR",
          "state": "EX",
          "countryCode": "2496",
          "cityCode": "9999999",
          "country": "USA"
        },
        "taxesSettings": {
          "icmsTaxPayer": false
        },
        "taxRegime": "notApplicable"
      },
      "establishment": {
        "name": "company_1_data",
        "businessName": "company_1_data",
        "type": "business",
        "federalTaxId": "49233848000150",
        "address": {
          "neighborhood": "Edificio Centro Comercial Itália 24o Andar",
          "street": "Rua Marechal Deodoro",
          "zipcode": "80010-010",
          "cityName": "Curitiba",
          "state": "PR",
          "countryCode": "1058",
          "country": "BRA",
          "number": "630"
        },
        "taxesSettings": {
          "icmsTaxPayer": false
        },
        "taxRegime": "individual"
      }
    },
    "goods": {
      "idDest": 3,
      "exportInfo": {
        "shippingState": "AC",
        "place": "testincotermlocationtestincotermlocationtestincotermlocation"
      }
    }
  },
  "lines": [
    {
      "lineCode": "___ignore___",
      "useType": "use or consumption",
      "operationType": "standardSales",
      "otherCostAmount": 0.0,
      "freightAmount": 0.0,
      "insuranceAmount": 0.0,
      "lineTaxedDiscount": 0.0,
      "lineAmount": 15.0,
      "lineUnitPrice": 15.0,
      "numberOfItems": 1.0,
      "itemDescriptor": {
        "description": "[PROD1] Product",
        "cean": "",
        "cest": "",
        "source": "0",
        "productType": "FOR PRODUCT",
        "hsCode": "49011000",
        "unitTaxable": "Units",
        "unit": "Units",
        "manufacturerEquivalent": false,
        "appropriateIPIcreditWhenInGoing": false,
        "notSubjectToIcmsSt": false,
        "isIcmsStSubstitute": false,
        "appropriateICMScreditWhenInGoing": false,
        "appropriatePISCOFINScreditWhenInGoing": false
      },
      "goods": {
          "entityOwnProduction": false
      },
      "itemCode": "PROD1"
    }
  ]
}
