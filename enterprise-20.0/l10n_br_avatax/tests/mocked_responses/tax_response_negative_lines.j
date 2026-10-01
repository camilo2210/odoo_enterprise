{
    "header": {
        "transactionDate": "2025-02-05",
        "amountCalcType": "gross",
        "documentCode": "account.move_99",
        "messageType": "goods",
        "companyLocation": "49233848000150",
        "operationType": "standardSales",
        "locations": {
            "entity": {
                "name": "Avatax Brazil Test Partner",
                "businessName": "Avatax Brazil Test Partner",
                "type": "individual",
                "address": {
                    "neighborhood": "Cristo Rei",
                    "street": "Avenida SAP",
                    "zipcode": "93022-718",
                    "cityName": "S\\u00e3o Leopoldo",
                    "state": "RS",
                    "country": "BRA",
                    "countryCode": "1058",
                    "number": "188"
                },
                "taxRegime": "individual"
            },
            "establishment": {
                "name": "BR Company",
                "businessName": "BR Company",
                "type": "business",
                "federalTaxId": "49233848000150",
                "stateTaxId": "9102799558",
                "address": {
                    "neighborhood": "Centro",
                    "street": "Rua Marechal Deodoro 630, Conjunto",
                    "zipcode": "80010-010",
                    "cityName": "Curitiba",
                    "state": "PR",
                    "country": "BRA",
                    "countryCode": "1058",
                    "number": "2401",
                    "phone": "+55 11 96123-4567",
                    "email": "info@company.brexample.com",
                    "cityCode": 4106902
                },
                "activitySector": {
                    "code": "service",
                    "ActivitySector_CNAE": {
                        "code": "6209100"
                    }
                },
                "taxRegime": "estimatedProfit",
                "taxesSettings": {
                    "icmsTaxPayer": true,
                    "pisCofinsAssetCalcBase": "D",
                    "pisCofinsReliefZF": false,
                    "cofinsSubjectTo": "T",
                    "csllSubjectTo": "T",
                    "pisSubjectTo": "T",
                    "pCredSN": 0,
                    "pisCofinsIcmsTaxRelief": true,
                    "pisCofinsIcmsTaxReliefMode": {
                        "icms": true,
                        "icmsFcp": false,
                        "icmsDifaDest": false,
                        "icmsDifaDestFcp": false
                    },
                    "pisCofinsIcmsTaxCreditRelief": false,
                    "pisCofinsIcmsTaxCreditReliefMode": {
                        "icms": false,
                        "icmsFcp": false,
                        "icmsDifaDest": false,
                        "icmsDifaDestFcp": false
                    },
                    "enableCprb": false,
                    "reduceIcmsTaxReliefToIPIBase": false
                }
            }
        },
        "enableCitationWarnings": false,
        "eDocCreatorType": "self",
        "eDocCreatorPerspective": true,
        "accountId": "73c836bc-3a10-4ae9-83e1-68fad0551a15",
        "subscriptionId": "40423965-d124-49ec-bd07-3b65a25b2503",
        "goods": {
            "class": "VENDA DE MERCADORIA ADQUIRIDA OU RECEBIDA DE TERCEIROS",
            "goal": "Normal",
            "tpImp": "1"
        },
        "additionalInfo": {
            "complementaryInfo": "PIS/COFINS com al\\u00edquota zero conforme: \\'Lei n\\u00ba 10.865/2004, Artigo 28, Inciso VI, inclu\\u00eddo pela Lei n\\u00ba 11.033/2004\\'"
        }
    },
    "lines": [
        {
            "lineCode": 285,
            "useType": "resale",
            "operationType": "standardSales",
            "otherCostAmount": 0,
            "freightAmount": 0,
            "insuranceAmount": 0,
            "lineTaxedDiscount": 37.5,
            "lineAmount": 100,
            "lineUnitPrice": 100,
            "numberOfItems": 1,
            "itemDescriptor": {
                "description": "Regular Consumable Product",
                "cean": "",
                "cnae": "6209100",
                "cest": "",
                "source": "0",
                "productType": "FOR MERCHANDISE",
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
                "entityOwnProduction": false,
                "indTotType": true,
                "entityIcmsStSubstitute": "default",
                "subjectToIPIonInbound": true
            },
            "overwrite": "no",
            "taxDetails": [
                {
                    "jurisdictionName": "Brazil",
                    "jurisdictionType": "Country",
                    "taxImpact": {
                        "impactOnFinalPrice": "Included",
                        "impactOnNetAmount": "Included",
                        "accounting": "none"
                    },
                    "taxType": "cofins",
                    "citation": "PIS/COFINS com al\\u00edquota zero conforme: \\'Lei n\\u00ba 10.865/2004, Artigo 28, Inciso VI, inclu\\u00eddo pela Lei n\\u00ba 11.033/2004\\'",
                    "citationId": "1f0f4a6e-4e31-41b5-9d6a-14f36bf00b34",
                    "subtotalTaxable": 55,
                    "rate": 0,
                    "tax": 0,
                    "exemptionCode": "",
                    "cst": "06",
                    "calcMode": "rate",
                    "isCustomCitation": false
                },
                {
                    "jurisdictionName": "Paran\\u00e1",
                    "jurisdictionType": "State",
                    "taxImpact": {
                        "impactOnFinalPrice": "Included",
                        "impactOnNetAmount": "Included",
                        "accounting": "liability"
                    },
                    "taxType": "icms",
                    "citation": "ICMS/PR_Decreto n\\u00ba 7.871/2017, Artigo 18, Inciso I",
                    "citationId": "cbc8af8a-36cc-4acc-93be-649d0db6514f",
                    "subtotalTaxable": 62.5,
                    "rate": 12,
                    "tax": 7.5,
                    "exemptionCode": "",
                    "source": "0",
                    "cst": "00",
                    "modBC": "3",
                    "isCustomCitation": false
                },
                {
                    "jurisdictionName": "Brazil",
                    "jurisdictionType": "Country",
                    "taxImpact": {
                        "impactOnFinalPrice": "Included",
                        "impactOnNetAmount": "Included",
                        "accounting": "none"
                    },
                    "taxType": "pis",
                    "citation": "PIS/COFINS com al\\u00edquota zero conforme: \\'Lei n\\u00ba 10.865/2004, Artigo 28, Inciso VI, inclu\\u00eddo pela Lei n\\u00ba 11.033/2004\\'",
                    "citationId": "85119944-8343-471d-b952-d49f77cb4277",
                    "subtotalTaxable": 55,
                    "rate": 0,
                    "tax": 0,
                    "exemptionCode": "",
                    "cst": "06",
                    "calcMode": "rate",
                    "isCustomCitation": false
                }
            ],
            "cfop": 6102,
            "lineAdditionalInfo": "",
            "lineNetFigure": 92.5
        },
        {
            "lineCode": 286,
            "useType": "resale",
            "operationType": "standardSales",
            "otherCostAmount": 0,
            "freightAmount": 0,
            "insuranceAmount": 0,
            "lineTaxedDiscount": 18.75,
            "lineAmount": 50,
            "lineUnitPrice": 50,
            "numberOfItems": 1,
            "itemDescriptor": {
                "description": "Regular Consumable Product",
                "cean": "",
                "cnae": "6209100",
                "cest": "",
                "source": "0",
                "productType": "FOR MERCHANDISE",
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
                "entityOwnProduction": false,
                "indTotType": true,
                "entityIcmsStSubstitute": "default",
                "subjectToIPIonInbound": true
            },
            "overwrite": "no",
            "taxDetails": [
                {
                    "jurisdictionName": "Brazil",
                    "jurisdictionType": "Country",
                    "taxImpact": {
                        "impactOnFinalPrice": "Included",
                        "impactOnNetAmount": "Included",
                        "accounting": "none"
                    },
                    "taxType": "cofins",
                    "citation": "PIS/COFINS com al\\u00edquota zero conforme: \\'Lei n\\u00ba 10.865/2004, Artigo 28, Inciso VI, inclu\\u00eddo pela Lei n\\u00ba 11.033/2004\\'",
                    "citationId": "1f0f4a6e-4e31-41b5-9d6a-14f36bf00b34",
                    "subtotalTaxable": 27.5,
                    "rate": 0,
                    "tax": 0,
                    "exemptionCode": "",
                    "cst": "06",
                    "calcMode": "rate",
                    "isCustomCitation": false
                },
                {
                    "jurisdictionName": "Paran\\u00e1",
                    "jurisdictionType": "State",
                    "taxImpact": {
                        "impactOnFinalPrice": "Included",
                        "impactOnNetAmount": "Included",
                        "accounting": "liability"
                    },
                    "taxType": "icms",
                    "citation": "ICMS/PR_Decreto n\\u00ba 7.871/2017, Artigo 18, Inciso I",
                    "citationId": "cbc8af8a-36cc-4acc-93be-649d0db6514f",
                    "subtotalTaxable": 31.25,
                    "rate": 12,
                    "tax": 3.75,
                    "exemptionCode": "",
                    "source": "0",
                    "cst": "00",
                    "modBC": "3",
                    "isCustomCitation": false
                },
                {
                    "jurisdictionName": "Brazil",
                    "jurisdictionType": "Country",
                    "taxImpact": {
                        "impactOnFinalPrice": "Included",
                        "impactOnNetAmount": "Included",
                        "accounting": "none"
                    },
                    "taxType": "pis",
                    "citation": "PIS/COFINS com al\\u00edquota zero conforme: \\'Lei n\\u00ba 10.865/2004, Artigo 28, Inciso VI, inclu\\u00eddo pela Lei n\\u00ba 11.033/2004\\'",
                    "citationId": "85119944-8343-471d-b952-d49f77cb4277",
                    "subtotalTaxable": 27.5,
                    "rate": 0,
                    "tax": 0,
                    "exemptionCode": "",
                    "cst": "06",
                    "calcMode": "rate",
                    "isCustomCitation": false
                }
            ],
            "cfop": 6102,
            "lineAdditionalInfo": "",
            "lineNetFigure": 46.25
        },
        {
            "lineCode": 287,
            "useType": "resale",
            "operationType": "standardSales",
            "otherCostAmount": 0,
            "freightAmount": 0,
            "insuranceAmount": 0,
            "lineTaxedDiscount": 3.75,
            "lineAmount": 10,
            "lineUnitPrice": 10,
            "numberOfItems": 1,
            "itemDescriptor": {
                "description": "Regular Consumable Product",
                "cean": "",
                "cnae": "6209100",
                "cest": "",
                "source": "0",
                "productType": "FOR MERCHANDISE",
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
                "entityOwnProduction": false,
                "indTotType": true,
                "entityIcmsStSubstitute": "default",
                "subjectToIPIonInbound": true
            },
            "overwrite": "no",
            "taxDetails": [
                {
                    "jurisdictionName": "Brazil",
                    "jurisdictionType": "Country",
                    "taxImpact": {
                        "impactOnFinalPrice": "Included",
                        "impactOnNetAmount": "Included",
                        "accounting": "none"
                    },
                    "taxType": "cofins",
                    "citation": "PIS/COFINS com al\\u00edquota zero conforme: \\'Lei n\\u00ba 10.865/2004, Artigo 28, Inciso VI, inclu\\u00eddo pela Lei n\\u00ba 11.033/2004\\'",
                    "citationId": "1f0f4a6e-4e31-41b5-9d6a-14f36bf00b34",
                    "subtotalTaxable": 5.5,
                    "rate": 0,
                    "tax": 0,
                    "exemptionCode": "",
                    "cst": "06",
                    "calcMode": "rate",
                    "isCustomCitation": false
                },
                {
                    "jurisdictionName": "Paran\\u00e1",
                    "jurisdictionType": "State",
                    "taxImpact": {
                        "impactOnFinalPrice": "Included",
                        "impactOnNetAmount": "Included",
                        "accounting": "liability"
                    },
                    "taxType": "icms",
                    "citation": "ICMS/PR_Decreto n\\u00ba 7.871/2017, Artigo 18, Inciso I",
                    "citationId": "cbc8af8a-36cc-4acc-93be-649d0db6514f",
                    "subtotalTaxable": 6.25,
                    "rate": 12,
                    "tax": 0.75,
                    "exemptionCode": "",
                    "source": "0",
                    "cst": "00",
                    "modBC": "3",
                    "isCustomCitation": false
                },
                {
                    "jurisdictionName": "Brazil",
                    "jurisdictionType": "Country",
                    "taxImpact": {
                        "impactOnFinalPrice": "Included",
                        "impactOnNetAmount": "Included",
                        "accounting": "none"
                    },
                    "taxType": "pis",
                    "citation": "PIS/COFINS com al\\u00edquota zero conforme: \\'Lei n\\u00ba 10.865/2004, Artigo 28, Inciso VI, inclu\\u00eddo pela Lei n\\u00ba 11.033/2004\\'",
                    "citationId": "85119944-8343-471d-b952-d49f77cb4277",
                    "subtotalTaxable": 5.5,
                    "rate": 0,
                    "tax": 0,
                    "exemptionCode": "",
                    "cst": "06",
                    "calcMode": "rate",
                    "isCustomCitation": false
                }
            ],
            "cfop": 6102,
            "lineAdditionalInfo": "",
            "lineNetFigure": 9.25
        }
    ],
    "version": "3",
    "processingInfo": {
        "versionId": "26.2.1",
        "duration": "8.376",
        "env": "sbx",
        "authMS": 7.5174,
        "retrieveDataMS": 214.8066,
        "taxDiscoveryMS": 172.1633,
        "calculationMS": 8.3755,
        "invoiceSubmitMS": 0.0133,
        "totalMS": 237.8346
    },
    "summary": {
        "numberOfLines": 3,
        "totalLineAmounts": 160,
        "totalTaxedDiscounts": 60,
        "totalUntaxedDiscounts": 0,
        "totalInsurances": 0,
        "totalFreights": 0,
        "totalOtherCosts": 0,
        "totalUnTaxedOtherCosts": 0,
        "totalInvoice": 100,
        "taxByType": {
            "cofins": {
                "tax": 0,
                "subtotalTaxable": 88,
                "jurisdictions": [
                    {
                        "jurisdictionName": "Brazil",
                        "jurisdictionType": "Country",
                        "tax": 0
                    }
                ]
            },
            "icms": {
                "tax": 12,
                "subtotalTaxable": 100,
                "jurisdictions": [
                    {
                        "jurisdictionName": "Paran\\u00e1",
                        "jurisdictionType": "State",
                        "tax": 12
                    }
                ]
            },
            "pis": {
                "tax": 0,
                "subtotalTaxable": 88,
                "jurisdictions": [
                    {
                        "jurisdictionName": "Brazil",
                        "jurisdictionType": "Country",
                        "tax": 0
                    }
                ]
            }
        },
        "taxImpactHighlights": {
            "included": [
                {
                    "taxType": "cofins",
                    "tax": 0,
                    "subtotalTaxable": 88
                },
                {
                    "taxType": "icms",
                    "tax": 12,
                    "subtotalTaxable": 100
                },
                {
                    "taxType": "pis",
                    "tax": 0,
                    "subtotalTaxable": 88
                }
            ],
            "added": [],
            "subtracted": [],
            "withheld": [],
            "informative": []
        }
    },
    "input": {
        "header": {
            "transactionDate": "2026-02-05",
            "amountCalcType": "gross",
            "documentCode": "account.move_99",
            "messageType": "goods",
            "companyLocation": "49233848000150",
            "operationType": "standardSales",
            "locations": {
                "entity": {
                    "name": "BR Company Customer",
                    "businessName": "BR Company Customer",
                    "type": "business",
                    "federalTaxId": "51494569013170",
                    "address": {
                        "neighborhood": "Curitaba",
                        "street": "Av. Presidente Vargas",
                        "zipcode": "30071-001",
                        "cityName": "Belo Horizonte",
                        "state": "MG",
                        "country": "BRA",
                        "countryCode": "1058",
                        "number": "592",
                        "cityCode": 3106200
                    },
                    "activitySector": {
                        "code": "industry"
                    },
                    "taxRegime": "simplified",
                    "taxesSettings": {
                        "icmsTaxPayer": true
                    }
                },
                "establishment": {
                    "name": "BR Company",
                    "businessName": "BR Company",
                    "type": "business",
                    "federalTaxId": "49233848000150",
                    "stateTaxId": "9102799558",
                    "address": {
                        "neighborhood": "Centro",
                        "street": "Rua Marechal Deodoro 630, Conjunto",
                        "zipcode": "80010-010",
                        "cityName": "Curitiba",
                        "state": "PR",
                        "country": "BRA",
                        "countryCode": "1058",
                        "number": "2401",
                        "phone": "+55 11 96123-4567",
                        "email": "info@company.brexample.com",
                        "cityCode": 4106902
                    },
                    "activitySector": {
                        "code": "service",
                        "ActivitySector_CNAE": {
                            "code": "6209100"
                        }
                    },
                    "taxRegime": "estimatedProfit",
                    "taxesSettings": {
                        "icmsTaxPayer": true,
                        "pisCofinsAssetCalcBase": "D",
                        "pisCofinsReliefZF": false,
                        "cofinsSubjectTo": "T",
                        "csllSubjectTo": "T",
                        "pisSubjectTo": "T",
                        "pCredSN": 0,
                        "pisCofinsIcmsTaxRelief": true,
                        "pisCofinsIcmsTaxReliefMode": {
                            "icms": true,
                            "icmsFcp": false,
                            "icmsDifaDest": false,
                            "icmsDifaDestFcp": false
                        },
                        "pisCofinsIcmsTaxCreditRelief": false,
                        "pisCofinsIcmsTaxCreditReliefMode": {
                            "icms": false,
                            "icmsFcp": false,
                            "icmsDifaDest": false,
                            "icmsDifaDestFcp": false
                        },
                        "enableCprb": false,
                        "reduceIcmsTaxReliefToIPIBase": false
                    }
                }
            },
            "enableCitationWarnings": false,
            "eDocCreatorType": "self",
            "eDocCreatorPerspective": true,
            "accountId": "73c836bc-3a10-4ae9-83e1-68fad0551a15",
            "subscriptionId": "40423965-d124-49ec-bd07-3b65a25b2503",
            "goods": {}
        },
        "lines": [
            {
                "lineCode": 285,
                "useType": "resale",
                "operationType": "standardSales",
                "otherCostAmount": 0,
                "freightAmount": 0,
                "insuranceAmount": 0,
                "lineTaxedDiscount": 37.5,
                "lineAmount": 100,
                "lineUnitPrice": 100,
                "numberOfItems": 1,
                "itemDescriptor": {
                    "description": "Regular Consumable Product",
                    "cean": "",
                    "cnae": "6209100",
                    "cest": "",
                    "source": "0",
                    "productType": "FOR MERCHANDISE",
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
                    "entityOwnProduction": false,
                    "indTotType": true,
                    "entityIcmsStSubstitute": "default"
                },
                "overwrite": "no"
            },
            {
                "lineCode": 286,
                "useType": "resale",
                "operationType": "standardSales",
                "otherCostAmount": 0,
                "freightAmount": 0,
                "insuranceAmount": 0,
                "lineTaxedDiscount": 18.75,
                "lineAmount": 50,
                "lineUnitPrice": 50,
                "numberOfItems": 1,
                "itemDescriptor": {
                    "description": "Regular Consumable Product",
                    "cean": "",
                    "cnae": "6209100",
                    "cest": "",
                    "source": "0",
                    "productType": "FOR MERCHANDISE",
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
                    "entityOwnProduction": false,
                    "indTotType": true,
                    "entityIcmsStSubstitute": "default"
                },
                "overwrite": "no"
            },
            {
                "lineCode": 287,
                "useType": "resale",
                "operationType": "standardSales",
                "otherCostAmount": 0,
                "freightAmount": 0,
                "insuranceAmount": 0,
                "lineTaxedDiscount": 3.75,
                "lineAmount": 10,
                "lineUnitPrice": 10,
                "numberOfItems": 1,
                "itemDescriptor": {
                    "description": "Regular Consumable Product",
                    "cean": "",
                    "cnae": "6209100",
                    "cest": "",
                    "source": "0",
                    "productType": "FOR MERCHANDISE",
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
                    "entityOwnProduction": false,
                    "indTotType": true,
                    "entityIcmsStSubstitute": "default"
                },
                "overwrite": "no"
            }
        ],
        "version": "3"
    }
}
