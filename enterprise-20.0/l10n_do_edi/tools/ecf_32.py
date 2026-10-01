import odoo.addons.l10n_do_edi.tools.ecf_common as common

IdDoc = {
    'TipoeCF': {},
    'eNCF': {},
    'IndicadorMontoGravado': {},
    'TipoIngresos': {},
    'TipoPago': {},
    'FechaLimitePago': {},
}

Comprador = {
    'RNCComprador': {},
    'IdentificadorExtranjero': {},
    'RazonSocialComprador': {},
}

Totales = {
    'MontoGravadoTotal': {},
    'MontoGravadoI1': {},
    'MontoGravadoI2': {},
    'MontoGravadoI3': {},
    'MontoExento': {},
    'ITBIS1': {},
    'ITBIS2': {},
    'ITBIS3': {},
    'TotalITBIS': {},
    'TotalITBIS1': {},
    'TotalITBIS2': {},
    'TotalITBIS3': {},
    'MontoImpuestoAdicional': {},
    'ImpuestosAdicionales': common.ImpuestosAdicionales,
    'MontoTotal': {},
    'MontoNoFacturable': {},
}

Item = {
    'NumeroLinea': {},
    'IndicadorFacturacion': {},
    'NombreItem': {},
    'IndicadorBienoServicio': {},
    'DescripcionItem': {},
    'CantidadItem': {},
    'PrecioUnitarioItem': {},
    'DescuentoMonto': {},
    'TablaSubDescuento': common.TablaSubDescuento,
    'OtraMonedaDetalle': common.OtraMonedaDetalle,
    'MontoItem': {},
}

Encabezado = {
    'Version': {},
    'IdDoc': IdDoc,
    'Emisor': common.Emisor,
    'Comprador': Comprador,
    'Totales': Totales,
    'OtraMoneda': common.OtraMoneda,
}

DetallesItems = {
    'Item': Item,
}

ECF = {
    '_tag': 'ECF',
    'Encabezado': Encabezado,
    'DetallesItems': DetallesItems,
    'FechaHoraFirma': {},
}
