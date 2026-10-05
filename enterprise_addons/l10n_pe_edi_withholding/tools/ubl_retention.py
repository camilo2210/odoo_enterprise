import odoo.addons.account_edi_ubl_cii.tools.ubl_21_common as cac

PeRetentionInformation = {
    'sac:SUNATRetentionAmount': {},
    'sac:SUNATRetentionDate': {},
    'sac:SUNATNetTotalPaid': {},
    'cac:ExchangeRate': cac.ExchangeRate,
}

PeRetentionDocumentReference = {
    'cbc:ID': {},
    'cbc:IssueDate': {},
    'cbc:TotalInvoiceAmount': {},
    'cac:Payment': cac.PrepaidPayment,
    'sac:SUNATRetentionInformation': PeRetentionInformation,
}

PeRetention = {
    '_tag': 'Retention',
    'ext:UBLExtensions': {},
    'cbc:UBLVersionID': {},
    'cbc:CustomizationID': {},
    'cac:Signature': cac.Signature,
    'cbc:ID': {},
    'cbc:IssueDate': {},
    'cac:AgentParty': cac.Party,
    'cac:ReceiverParty': cac.Party,
    'sac:SUNATRetentionSystemCode': {},
    'sac:SUNATRetentionPercent': {},
    'cbc:Note': {},
    'cbc:TotalInvoiceAmount': {},
    'sac:SUNATTotalPaid': {},
    'sac:SUNATRetentionDocumentReference': PeRetentionDocumentReference,
}
