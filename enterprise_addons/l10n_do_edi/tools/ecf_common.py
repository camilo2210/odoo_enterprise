Emisor = {
    'RNCEmisor': {},
    'RazonSocialEmisor': {},
    'DireccionEmisor': {},
    'FechaEmision': {},
}

ImpuestoAdicional = {
    'TipoImpuesto': {},
    'TasaImpuestoAdicional': {},
    'OtrosImpuestosAdicionales': {},
}

ImpuestosAdicionales = {
    'ImpuestoAdicional': ImpuestoAdicional,
}

ImpuestoAdicionalOtraMoneda = {
    'TipoImpuestoOtraMoneda': {},
    'TasaImpuestoAdicionalOtraMoneda': {},
    'OtrosImpuestosAdicionalesOtraMoneda': {},
}

ImpuestosAdicionalesOtraMoneda = {
    'ImpuestoAdicionalOtraMoneda': ImpuestoAdicionalOtraMoneda,
}

OtraMoneda = {
    'TipoMoneda': {},
    'TipoCambio': {},
    'MontoGravadoTotalOtraMoneda': {},
    'MontoGravado1OtraMoneda': {},
    'MontoGravado2OtraMoneda': {},
    'MontoGravado3OtraMoneda': {},
    'MontoExentoOtraMoneda': {},
    'TotalITBISOtraMoneda': {},
    'TotalITBIS1OtraMoneda': {},
    'TotalITBIS2OtraMoneda': {},
    'TotalITBIS3OtraMoneda': {},
    'MontoImpuestoAdicionalOtraMoneda': {},
    'ImpuestosAdicionalesOtraMoneda': ImpuestosAdicionalesOtraMoneda,
    'MontoTotalOtraMoneda': {},
}

Retencion = {
    'IndicadorAgenteRetencionoPercepcion': {},
    'MontoITBISRetenido': {},
    'MontoISRRetenido': {},
}

SubDescuento = {
    'TipoSubDescuento': {},
    'SubDescuentoPorcentaje': {},
    'MontoSubDescuento': {},
}

TablaSubDescuento = {
    'SubDescuento': SubDescuento,
}

OtraMonedaDetalle = {
    'PrecioOtraMoneda': {},
    'DescuentoOtraMoneda': {},
    'MontoItemOtraMoneda': {},
}

InformacionReferencia = {
    'NCFModificado': {},
    'FechaNCFModificado': {},
    'CodigoModificacion': {},
    'RazonModificacion': {},
}
