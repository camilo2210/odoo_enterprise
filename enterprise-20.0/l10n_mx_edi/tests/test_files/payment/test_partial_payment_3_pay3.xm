<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4" xmlns:pago20="http://www.sat.gob.mx/Pagos20" xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" Certificado="___ignore___" Exportacion="01" Fecha="___ignore___" Folio="___ignore___" LugarExpedicion="20914" Moneda="XXX" NoCertificado="___ignore___" Sello="___ignore___" Serie="___ignore___" SubTotal="0" TipoDeComprobante="P" Total="0" Version="4.0" xsi:schemaLocation="___ignore___">
	<cfdi:Emisor Nombre="ESCUELA KEMPER URGATE" RegimenFiscal="601" Rfc="EKU9003173C9"/>
	<cfdi:Receptor DomicilioFiscalReceptor="33826" Nombre="INMOBILIARIA CVA" RegimenFiscalReceptor="601" Rfc="ICV060329BY0" UsoCFDI="CP01"/>
	<cfdi:Conceptos>
		<cfdi:Concepto Cantidad="1" ClaveProdServ="84111506" ClaveUnidad="ACT" Descripcion="Pago" Importe="0" ObjetoImp="01" ValorUnitario="0"/>
	</cfdi:Conceptos>
	<cfdi:Complemento>
		<pago20:Pagos Version="2.0">
			<pago20:Totales MontoTotalPagos="116.00" TotalTrasladosBaseIVA16="100.00" TotalTrasladosImpuestoIVA16="16.00"/>
			<pago20:Pago FechaPago="___ignore___" FormaDePagoP="01" MonedaP="USD" Monto="2030.00" NumOperacion="___ignore___" TipoCambioP="0.057143">
				<pago20:DoctoRelacionado EquivalenciaDR="0.0571428571" Folio="___ignore___" IdDocumento="___ignore___" ImpPagado="116.00" ImpSaldoAnt="815.41" ImpSaldoInsoluto="699.41" MonedaDR="MXN" NumParcialidad="3" ObjetoImpDR="02" Serie="___ignore___">
					<pago20:ImpuestosDR>
						<pago20:TrasladosDR>
							<pago20:TrasladoDR BaseDR="100.000000" ImporteDR="16.000000" ImpuestoDR="002" TasaOCuotaDR="0.160000" TipoFactorDR="Tasa"/>
						</pago20:TrasladosDR>
					</pago20:ImpuestosDR>
				</pago20:DoctoRelacionado>
				<pago20:ImpuestosP>
					<pago20:TrasladosP>
						<pago20:TrasladoP BaseP="1750.000001" ImporteP="280.000000" ImpuestoP="002" TasaOCuotaP="0.160000" TipoFactorP="Tasa"/>
					</pago20:TrasladosP>
				</pago20:ImpuestosP>
			</pago20:Pago>
		</pago20:Pagos>
		<tfd:TimbreFiscalDigital FechaTimbrado="___ignore___" NoCertificadoSAT="___ignore___" RfcProvCertif="___ignore___" SelloCFD="___ignore___" SelloSAT="___ignore___" UUID="___ignore___" Version="1.1" xsi:schemaLocation="___ignore___"/>
	</cfdi:Complemento>
</cfdi:Comprobante>
