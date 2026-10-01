<?xml version="1.0" encoding="utf-8" ?>
<odoo>
	<template id="report_social_balance">
		<t t-call="web.html_container">
			<t t-foreach="docs" t-as="wizard">
				<t t-call="web.external_layout">
					<t t-set="wizard" t-value="wizard.with_context(lang=wizard.env.lang)"/>
					<div class="page container-fluid">
						<div class="mt-4 row text-center fw-bold">
							<div class="col-12">
								<div>SOCIAL BALANCE SHEET - COMPLETE SCHEME</div>
								<div class="mt-2">Please find attached some data that will be useful to you to establish the Social Report for the accounting year noted below. The Social Report for the previous year may be useful for you to complete information concerning the previous accounting year.</div>
							</div>
						</div>
						<div class="mt-4 row">
							<div class="col-12">
								<div class="fw-bold">Identification of the company</div>
							</div>
						</div>
						<div class="row">
							<div class="col-12 border p-2">
								<div class="mb-2">VAT Number: <t t-out="wizard.company_id.vat"/></div>
								<div class="mb-2">ONSS Number: <t t-out="wizard.company_id._get_payroll_config(wizard.date_from).onss_registration_number"/></div>
								<div class="mb-2">Numbers of joint committees: 20000</div>
								<div class="mb-2">Established on: <span t-field="wizard.create_date"/></div>
								<div class="mb-2">Period: From <span t-field="wizard.date_from"/> To <span t-field="wizard.date_to"/></div>
								<div class="mb-2">Currency: <t t-out="wizard.company_id.currency_id.name"/></div>
							</div>
						</div>
					</div>
					<t t-value="data['sbs_data']['year']" t-set="year"/>
					<t t-value="data['sbs_data']['social_balance_sheet']" t-set="data"/>
					<div class="page container-fluid">
						<div style="page-break-before: always;">
							<div class="mt-4 row">
								<h1>Period - Year <t t-out="year"/></h1>
							</div>
							<div class="mb-4 row">
								<div class="col-12">
									<h2><b>Status of employed persons</b></h2>
									<h3>Workers for whom the company has submitted a DIMONA declaration or who are registered in the general staff register</h3>
								</div>
							</div>
							<table class="o_ignore_layout_styling table table-borderless table-sm">
								<thead class="border-bottom">
									<tr>
										<th scope="col"><b>During the exercise</b></th>
										<th scope="col" class="text-end"><b>Code</b></th>
										<th scope="col" class="text-end"><b>Total</b></th>
										<th scope="col" class="text-end"><b>Male</b></th>
										<th scope="col" class="text-end"><b>Female</b></th>
									</tr>
								</thead>
								<tbody align="right">
									<tr>
										<th><b>Average number of workers</b></th>
										<td/>
										<td/>
										<td/>
										<td/>
									</tr>
									<tr>
										<th class="ps-4">Full-time workers</th>
										<td>1001</td>
										<td><t t-out="round(data['1001_total'], 2)"/></td>
										<td><t t-out="round(data['1001_male'], 2)"/></td>
										<td><t t-out="round(data['1001_female'], 2)"/></td>
									</tr>
									<tr>
										<th class="ps-4">Part-time workers</th>
										<td>1002</td>
										<td><t t-out="round(data['1002_total'], 2)"/></td>
										<td><t t-out="round(data['1002_male'], 2)"/></td>
										<td><t t-out="round(data['1002_female'], 2)"/></td>
									</tr>
									<tr>
										<th class="ps-4">Total in FTEs</th>
										<td>1003</td>
										<td><t t-out="round(data['1003_total'], 2)"/></td>
										<td><t t-out="round(data['1003_male'], 2)"/></td>
										<td><t t-out="round(data['1003_female'], 2)"/></td>
									</tr>
									<tr>
										<th><b>Number of hours actually worked</b></th>
										<td/>
										<td/>
										<td/>
										<td/>
									</tr>
									<tr>
										<th class="ps-4">Full time</th>
										<td>1011</td>
										<td><t t-out="round(data['1011_total'], 2)"/></td>
										<td><t t-out="round(data['1011_male'], 2)"/></td>
										<td><t t-out="round(data['1011_female'], 2)"/></td>
									</tr>
									<tr>
										<th class="ps-4">Part-time</th>
										<td>1012</td>
										<td><t t-out="round(data['1012_total'], 2)"/></td>
										<td><t t-out="round(data['1012_male'], 2)"/></td>
										<td><t t-out="round(data['1012_female'], 2)"/></td>
									</tr>
									<tr>
										<th class="ps-4">Total</th>
										<td>1013</td>
										<td><t t-out="round(data['1013_total'], 2)"/></td>
										<td><t t-out="round(data['1013_male'], 2)"/></td>
										<td><t t-out="round(data['1013_female'], 2)"/></td>
									</tr>
									<tr>
										<th><b>Staff Costs</b></th>
										<td/>
										<td/>
										<td/>
										<td/>
									</tr>
									<tr>
										<th class="ps-4">Full Time</th>
										<td>1021</td>
										<td><t t-options="{'widget': 'monetary', 'display_currency': wizard.company_id.currency_id}" t-out="round(data['102']['total_gross']['male']['full'] + data['102']['total_gross']['female']['full'], 2)"/></td>
										<td><t t-options="{'widget': 'monetary', 'display_currency': wizard.company_id.currency_id}" t-out="round(data['102']['total_gross']['male']['full'], 2)"/></td>
										<td><t t-options="{'widget': 'monetary', 'display_currency': wizard.company_id.currency_id}" t-out="round(data['102']['total_gross']['female']['full'], 2)"/></td>
									</tr>
									<tr>
										<th class="ps-4">Partial Time</th>
										<td>1022</td>
										<td><t t-options="{'widget': 'monetary', 'display_currency': wizard.company_id.currency_id}" t-out="round(data['102']['total_gross']['male']['part'] + data['102']['total_gross']['female']['part'], 2)"/></td>
										<td><t t-options="{'widget': 'monetary', 'display_currency': wizard.company_id.currency_id}" t-out="round(data['102']['total_gross']['male']['part'], 2)"/></td>
										<td><t t-options="{'widget': 'monetary', 'display_currency': wizard.company_id.currency_id}" t-out="round(data['102']['total_gross']['female']['part'], 2)"/></td>
									</tr>
									<tr>
										<th class="ps-4">Total</th>
										<td>1023</td>
										<td><t t-options="{'widget': 'monetary', 'display_currency': wizard.company_id.currency_id}" t-out="round(data['102']['total']['male']['full'] + data['102']['total']['female']['full'] + data['102']['total']['male']['part'] + data['102']['total']['female']['part'], 2)"/></td>
										<td><t t-options="{'widget': 'monetary', 'display_currency': wizard.company_id.currency_id}" t-out="round(data['102']['total']['male']['full'] + data['102']['total']['male']['part'], 2)"/></td>
										<td><t t-options="{'widget': 'monetary', 'display_currency': wizard.company_id.currency_id}" t-out="round(data['102']['total']['female']['full'] + data['102']['total']['female']['part'], 2)"/></td>
									</tr>
									<tr>
										<th><b>Benefits granted in addition to salary</b></th>
										<td>1033</td>
										<td><t t-options="{'widget': 'monetary', 'display_currency': wizard.company_id.currency_id}" t-out="round(data['103']['male'] + data['103']['female'], 2)"/></td>
										<td><t t-options="{'widget': 'monetary', 'display_currency': wizard.company_id.currency_id}" t-out="round(data['103']['male'], 2)"/></td>
										<td><t t-options="{'widget': 'monetary', 'display_currency': wizard.company_id.currency_id}" t-out="round(data['103']['female'], 2)"/></td>
									</tr>
								</tbody>
							</table>
							<table class="o_ignore_layout_styling table table-borderless table-sm">
								<thead class="border-bottom">
									<tr>
										<th scope="col"><b>At the end of the exercise</b></th>
										<th scope="col" class="text-end"><b>Code</b></th>
										<th scope="col" class="text-end"><b>Full Time</b></th>
										<th scope="col" class="text-end"><b>Part-Time</b></th>
										<th scope="col" class="text-end"><b>Total (FTE)</b></th>
									</tr>
								</thead>
								<tbody align="right">
									<tr>
										<th><b>Number of workers</b></th>
										<td>105</td>
										<td><t t-out="round(data['105']['full'], 2)"/></td>
										<td><t t-out="round(data['105']['part'], 2)"/></td>
										<td><t t-out="round(data['105']['fte'], 2)"/></td>
									</tr>
									<tr>
										<th><b>By contract type</b></th>
										<td></td>
										<td></td>
										<td></td>
										<td></td>
									</tr>
									<tr>
										<th class="ps-4">Permanent contract (CDI)</th>
										<td>110</td>
										<td><t t-out="round(data['110']['full'], 2)"/></td>
										<td><t t-out="round(data['110']['part'], 2)"/></td>
										<td><t t-out="round(data['110']['fte'], 2)"/></td>
									</tr>
									<tr>
										<th class="ps-4">Fixed term contract (CDD)</th>
										<td>111</td>
										<td><t t-out="round(data['111']['full'], 2)"/></td>
										<td><t t-out="round(data['111']['part'], 2)"/></td>
										<td><t t-out="round(data['111']['fte'], 2)"/></td>
									</tr>
									<tr>
										<th class="ps-4">Contract for the execution of a clearly defined work</th>
										<td>112</td>
										<td><t t-out="round(data['112']['full'], 2)"/></td>
										<td><t t-out="round(data['112']['part'], 2)"/></td>
										<td><t t-out="round(data['112']['fte'], 2)"/></td>
									</tr>
									<tr>
										<th class="ps-4">Replacement contract</th>
										<td>113</td>
										<td><t t-out="round(data['113']['full'], 2)"/></td>
										<td><t t-out="round(data['113']['part'], 2)"/></td>
										<td><t t-out="round(data['113']['fte'], 2)"/></td>
									</tr>
									<tr>
										<th><b>By sex and educational level</b></th>
										<td></td>
										<td></td>
										<td></td>
										<td></td>
									</tr>
									<tr>
										<th class="ps-4">Male</th>
										<td>120</td>
										<td><t t-out="round(data['120']['full'], 2)"/></td>
										<td><t t-out="round(data['120']['part'], 2)"/></td>
										<td><t t-out="round(data['120']['fte'], 2)"/></td>
									</tr>
									<tr>
										<th class="ps-5">Primary education</th>
										<td>1200</td>
										<td><t t-out="round(data['1200']['full'], 2)"/></td>
										<td><t t-out="round(data['1200']['part'], 2)"/></td>
										<td><t t-out="round(data['1200']['fte'], 2)"/></td>
									</tr>
									<tr>
										<th class="ps-5">Secondary education</th>
										<td>1201</td>
										<td><t t-out="round(data['1201']['full'], 2)"/></td>
										<td><t t-out="round(data['1201']['part'], 2)"/></td>
										<td><t t-out="round(data['1201']['fte'], 2)"/></td>
									</tr>
									<tr>
										<th class="ps-5">Non-university higher education</th>
										<td>1202</td>
										<td><t t-out="round(data['1202']['full'], 2)"/></td>
										<td><t t-out="round(data['1202']['part'], 2)"/></td>
										<td><t t-out="round(data['1202']['fte'], 2)"/></td>
									</tr>
									<tr>
										<th class="ps-5">University education</th>
										<td>1203</td>
										<td><t t-out="round(data['1203']['full'], 2)"/></td>
										<td><t t-out="round(data['1203']['part'], 2)"/></td>
										<td><t t-out="round(data['1203']['fte'], 2)"/></td>
									</tr>
									<tr>
										<th class="ps-4">Female</th>
										<td>121</td>
										<td><t t-out="round(data['121']['full'], 2)"/></td>
										<td><t t-out="round(data['121']['part'], 2)"/></td>
										<td><t t-out="round(data['121']['fte'], 2)"/></td>
									</tr>
									<tr>
										<th class="ps-5">Primary education</th>
										<td>1210</td>
										<td><t t-out="round(data['1210']['full'], 2)"/></td>
										<td><t t-out="round(data['1210']['part'], 2)"/></td>
										<td><t t-out="round(data['1210']['fte'], 2)"/></td>
									</tr>
									<tr>
										<th class="ps-5">Secondary education</th>
										<td>1211</td>
										<td><t t-out="round(data['1211']['full'], 2)"/></td>
										<td><t t-out="round(data['1211']['part'], 2)"/></td>
										<td><t t-out="round(data['1211']['fte'], 2)"/></td>
									</tr>
									<tr>
										<th class="ps-5">Non-university higher education</th>
										<td>1212</td>
										<td><t t-out="round(data['1212']['full'], 2)"/></td>
										<td><t t-out="round(data['1212']['part'], 2)"/></td>
										<td><t t-out="round(data['1212']['fte'], 2)"/></td>
									</tr>
									<tr>
										<th class="ps-5">University education</th>
										<td>1213</td>
										<td><t t-out="round(data['1213']['full'], 2)"/></td>
										<td><t t-out="round(data['1213']['part'], 2)"/></td>
										<td><t t-out="round(data['1213']['fte'], 2)"/></td>
									</tr>
									<tr>
										<th><b>By professional category</b></th>
										<td></td>
										<td></td>
										<td></td>
										<td></td>
									</tr>
									<tr>
										<th class="ps-4">Management staff</th>
										<td>130</td>
										<td><t t-out="round(data['130']['full'], 2)"/></td>
										<td><t t-out="round(data['130']['part'], 2)"/></td>
										<td><t t-out="round(data['130']['fte'], 2)"/></td>
									</tr>
									<tr>
										<th class="ps-4">Employees</th>
										<td>134</td>
										<td><t t-out="round(data['134']['full'], 2)"/></td>
										<td><t t-out="round(data['134']['part'], 2)"/></td>
										<td><t t-out="round(data['134']['fte'], 2)"/></td>
									</tr>
									<tr>
										<th class="ps-4">Workers</th>
										<td>132</td>
										<td><t t-out="round(data['132']['full'], 2)"/></td>
										<td><t t-out="round(data['132']['part'], 2)"/></td>
										<td><t t-out="round(data['132']['fte'], 2)"/></td>
									</tr>
									<tr>
										<th class="ps-4">Others</th>
										<td>133</td>
										<td><t t-out="round(data['133']['full'], 2)"/></td>
										<td><t t-out="round(data['133']['part'], 2)"/></td>
										<td><t t-out="round(data['133']['fte'], 2)"/></td>
									</tr>
								</tbody>
							</table>
							<h3>Tempory Staff and personnel made available to the company</h3>
							<table class="o_ignore_layout_styling table table-borderless table-sm">
								<thead class="border-bottom">
									<tr>
										<th scope="col"><b>During the exercise</b></th>
										<th scope="col" class="text-end"><b>Code</b></th>
										<th scope="col" class="text-end"><b>Temporary staff</b></th>
										<th scope="col" class="text-end"><b>Personnel made available to the company</b></th>
									</tr>
								</thead>
								<tbody align="right">
									<tr>
										<th>Average number of occupied persons</th>
										<td>150</td>
										<td/>
										<td/>
									</tr>
									<tr>
										<th>Number of hours effectively worked</th>
										<td>151</td>
										<td/>
										<td/>
									</tr>
									<tr>
										<th>Cost for the company</th>
										<td>152</td>
										<td><t t-out="wizard.company_id.currency_id.symbol"/></td>
										<td><t t-out="wizard.company_id.currency_id.symbol"/></td>
									</tr>
								</tbody>
							</table>
							<h3>Staff movements during the exercise</h3>
							<table class="o_ignore_layout_styling table table-borderless table-sm">
								<thead class="border-bottom">
									<tr>
										<th scope="col"><b>Entries</b></th>
										<th scope="col" class="text-end"><b>Code</b></th>
										<th scope="col" class="text-end"><b>Full Time</b></th>
										<th scope="col" class="text-end"><b>Part-Time</b></th>
										<th scope="col" class="text-end"><b>Total (FTE)</b></th>
									</tr>
								</thead>
								<tbody align="right">
									<tr>
										<th><b>Total number</b></th>
										<td>205</td>
										<td><t t-out="round(data['205']['full'], 2)"/></td>
										<td><t t-out="round(data['205']['part'], 2)"/></td>
										<td><t t-out="round(data['205']['fte'], 2)"/></td>
									</tr>
									<tr>
										<th><b>By contract type</b></th>
										<td></td>
										<td></td>
										<td></td>
										<td></td>
									</tr>
									<tr>
										<th class="ps-4">Permanent contract (CDI)</th>
										<td>210</td>
										<td><t t-out="round(data['210']['full'], 2)"/></td>
										<td><t t-out="round(data['210']['part'], 2)"/></td>
										<td><t t-out="round(data['210']['fte'], 2)"/></td>
									</tr>
									<tr>
										<th class="ps-4">Fixed term contract (CDD)</th>
										<td>211</td>
										<td><t t-out="round(data['211']['full'], 2)"/></td>
										<td><t t-out="round(data['211']['part'], 2)"/></td>
										<td><t t-out="round(data['211']['fte'], 2)"/></td>
									</tr>
									<tr>
										<th class="ps-4">Contract for the execution of a clearly defined work</th>
										<td>212</td>
										<td><t t-out="round(data['212']['full'], 2)"/></td>
										<td><t t-out="round(data['212']['part'], 2)"/></td>
										<td><t t-out="round(data['212']['fte'], 2)"/></td>
									</tr>
									<tr>
										<th class="ps-4">Replacement contract</th>
										<td>213</td>
										<td><t t-out="round(data['213']['full'], 2)"/></td>
										<td><t t-out="round(data['213']['part'], 2)"/></td>
										<td><t t-out="round(data['213']['fte'], 2)"/></td>
									</tr>
								</tbody>
							</table>
							<table class="o_ignore_layout_styling table table-borderless table-sm">
								<thead class="border-bottom">
									<tr>
										<th scope="col"><b>Departures</b></th>
										<th scope="col" class="text-end"><b>Code</b></th>
										<th scope="col" class="text-end"><b>Full Time</b></th>
										<th scope="col" class="text-end"><b>Part-Time</b></th>
										<th scope="col" class="text-end"><b>Total (FTE)</b></th>
									</tr>
								</thead>
								<tbody align="right">
									<tr>
										<th><b>Total number</b></th>
										<td>305</td>
										<td><t t-out="round(data['305']['full'], 2)"/></td>
										<td><t t-out="round(data['305']['part'], 2)"/></td>
										<td><t t-out="round(data['305']['fte'], 2)"/></td>
									</tr>
									<tr>
										<th><b>By contract type</b></th>
										<td></td>
										<td></td>
										<td></td>
										<td></td>
									</tr>
									<tr>
										<th class="ps-4">Permanent contract (CDI)</th>
										<td>310</td>
										<td><t t-out="round(data['310']['full'], 2)"/></td>
										<td><t t-out="round(data['310']['part'], 2)"/></td>
										<td><t t-out="round(data['310']['fte'], 2)"/></td>
									</tr>
									<tr>
										<th class="ps-4">Fixed term contract (CDD)</th>
										<td>311</td>
										<td><t t-out="round(data['311']['full'], 2)"/></td>
										<td><t t-out="round(data['311']['part'], 2)"/></td>
										<td><t t-out="round(data['311']['fte'], 2)"/></td>
									</tr>
									<tr>
										<th class="ps-4">Contract for the execution of a clearly defined work</th>
										<td>312</td>
										<td><t t-out="round(data['312']['full'], 2)"/></td>
										<td><t t-out="round(data['312']['part'], 2)"/></td>
										<td><t t-out="round(data['312']['fte'], 2)"/></td>
									</tr>
									<tr>
										<th class="ps-4">Replacement contract</th>
										<td>313</td>
										<td><t t-out="round(data['313']['full'], 2)"/></td>
										<td><t t-out="round(data['313']['part'], 2)"/></td>
										<td><t t-out="round(data['313']['fte'], 2)"/></td>
									</tr>
									<tr>
										<th><b>By reason for termination of contract</b></th>
										<td></td>
										<td></td>
										<td></td>
										<td></td>
									</tr>
									<tr>
										<th class="ps-4">Pension</th>
										<td>340</td>
										<td><t t-out="round(data['340']['full'], 2)"/></td>
										<td><t t-out="round(data['340']['part'], 2)"/></td>
										<td><t t-out="round(data['340']['fte'], 2)"/></td>
									</tr>
									<tr>
										<th class="ps-4">Unemployment with company supplement</th>
										<td>341</td>
										<td><t t-out="round(data['341']['full'], 2)"/></td>
										<td><t t-out="round(data['341']['part'], 2)"/></td>
										<td><t t-out="round(data['341']['fte'], 2)"/></td>
									</tr>
									<tr>
										<th class="ps-4">Dismissal</th>
										<td>342</td>
										<td><t t-out="round(data['342']['full'], 2)"/></td>
										<td><t t-out="round(data['342']['part'], 2)"/></td>
										<td><t t-out="round(data['342']['fte'], 2)"/></td>
									</tr>
									<tr>
										<th class="ps-4">Another reason</th>
										<td>343</td>
										<td><t t-out="round(data['343']['full'], 2)"/></td>
										<td><t t-out="round(data['343']['part'], 2)"/></td>
										<td><t t-out="round(data['343']['fte'], 2)"/></td>
									</tr>
								</tbody>
							</table>
							<h3>Information on training for workers during the exercise</h3>
							<table class="o_ignore_layout_styling table table-borderless table-sm">
								<thead class="border-bottom">
									<tr>
										<th scope="col"><b>Formal continuous trainings at the employer's expense</b></th>
										<th scope="col" class="col-1 text-end"><b>Code</b></th>
										<th scope="col" class="col-2 text-end"><b>Male</b></th>
										<th scope="col" class="col-1 text-end"><b>Code</b></th>
										<th scope="col" class="col-2 text-end"><b>Female</b></th>
									</tr>
								</thead>
								<tbody align="right">
									<tr>
										<th>Number of Affected Employees</th>
										<td>5801</td>
										<td></td>
										<td>5811</td>
										<td></td>
									</tr>
									<tr>
										<th>Number of completed training hours</th>
										<td>5802</td>
										<td></td>
										<td>5812</td>
										<td></td>
									</tr>
									<tr>
										<th><b>Net cost for the company</b></th>
										<td>5803</td>
										<td><t t-out="wizard.company_id.currency_id.symbol"/></td>
										<td>5813</td>
										<td><t t-out="wizard.company_id.currency_id.symbol"/></td>
									</tr>
									<tr>
										<th class="ps-4">Gross cost directly linked to training</th>
										<td>58031</td>
										<td><t t-out="wizard.company_id.currency_id.symbol"/></td>
										<td>58131</td>
										<td><t t-out="wizard.company_id.currency_id.symbol"/></td>
									</tr>
									<tr>
										<th class="ps-4">Contributions paid and payments to collective funds</th>
										<td>58032</td>
										<td><t t-out="wizard.company_id.currency_id.symbol"/></td>
										<td>58132</td>
										<td><t t-out="wizard.company_id.currency_id.symbol"/></td>
									</tr>
									<tr>
										<th class="ps-4">Grants and other financial benefits received (to be deducted)</th>
										<td>58033</td>
										<td><t t-out="wizard.company_id.currency_id.symbol"/></td>
										<td>58133</td>
										<td><t t-out="wizard.company_id.currency_id.symbol"/></td>
									</tr>
								</tbody>
							</table>
							<table class="o_ignore_layout_styling table table-borderless table-sm">
								<thead class="border-bottom">
									<tr>
										<th scope="col"><b>Informal continuous trainings at the employer's expense</b></th>
										<th scope="col" class="col-1 text-end"><b>Code</b></th>
										<th scope="col" class="col-2 text-end"><b>Male</b></th>
										<th scope="col" class="col-1 text-end"><b>Code</b></th>
										<th scope="col" class="col-2 text-end"><b>Female</b></th>
									</tr>
								</thead>
								<tbody align="right">
									<tr>
										<th>Number of Affected Employees</th>
										<td>5821</td>
										<td></td>
										<td>5831</td>
										<td></td>
									</tr>
									<tr>
										<th>Number of completed training hours</th>
										<td>5822</td>
										<td></td>
										<td>5832</td>
										<td></td>
									</tr>
									<tr>
										<th>Net cost to the business</th>
										<td>5823</td>
										<td><t t-out="wizard.company_id.currency_id.symbol"/></td>
										<td>5833</td>
										<td><t t-out="wizard.company_id.currency_id.symbol"/></td>
									</tr>
								</tbody>
							</table>
							<table class="o_ignore_layout_styling table table-borderless table-sm">
								<thead class="border-bottom">
									<tr>
										<th scope="col"><b>Initial trainings at the employer's expense</b></th>
										<th scope="col" class="col-1 text-end"><b>Code</b></th>
										<th scope="col" class="col-2 text-end"><b>Male</b></th>
										<th scope="col" class="col-1 text-end"><b>Code</b></th>
										<th scope="col" class="col-2 text-end"><b>Female</b></th>
									</tr>
								</thead>
								<tbody align="right">
									<tr>
										<th>Number of Affected Employees</th>
										<td>5841</td>
										<td></td>
										<td>5851</td>
										<td></td>
									</tr>
									<tr>
										<th>Number of completed training hours</th>
										<td>5842</td>
										<td></td>
										<td>5852</td>
										<td></td>
									</tr>
									<tr>
										<th>Net cost to the business</th>
										<td>5843</td>
										<td><t t-out="wizard.company_id.currency_id.symbol"/></td>
										<td>5853</td>
										<td><t t-out="wizard.company_id.currency_id.symbol"/></td>
									</tr>
								</tbody>
							</table>
						</div>
					</div>
				</t>
			</t>
		</t>
	</template>
</odoo>
