from odoo import fields
from odoo.tests.common import TransactionCase, tagged


@tagged('-standard', 'external')
@tagged('at_install', '-post_install')  # LEGACY at_install
class CurrencyTestCase(TransactionCase):

    def setUp(self):
        super(CurrencyTestCase, self).setUp()
        # Each test will check the number of rates for USD
        self.currency_usd = self.env.ref('base.USD')
        self.test_company = self.env['res.company'].create({
            'name': 'Test Company',
            'currency_id': self.currency_usd.id,
        })

    def test_live_currency_update_ecb(self):
        self.test_company.currency_provider = 'ecb'
        rates_count = len(self.currency_usd.rate_ids)
        res = self.test_company.update_currency_rates()
        self.assertTrue(res)
        self.assertEqual(len(self.currency_usd.rate_ids), rates_count + 1)

    def test_live_currency_update_fta(self):
        self.test_company.currency_provider = 'fta'
        # testing Swiss Federal Tax Administration requires that Franc Suisse can be found
        # which is not the case in runbot/demo data as l10n_ch is not always installed
        self.env.ref('base.CHF').write({'active': True})
        rates_count = len(self.currency_usd.rate_ids)
        res = self.test_company.update_currency_rates()
        self.assertTrue(res)
        self.assertEqual(len(self.currency_usd.rate_ids), rates_count + 1)

    def test_live_currency_update_banxico(self):
        self.test_company.currency_provider = 'banxico'
        self.env.ref('base.MXN').write({'active': True})
        rates_count = len(self.currency_usd.rate_ids)
        res = self.test_company.update_currency_rates()
        self.assertTrue(res)
        self.assertEqual(len(self.currency_usd.rate_ids), rates_count + 1)

    def test_live_currency_update_boc(self):
        self.test_company.currency_provider = 'boc'
        rates_count = len(self.currency_usd.rate_ids)
        res = self.test_company.update_currency_rates()
        self.assertTrue(res)
        self.assertEqual(len(self.currency_usd.rate_ids), rates_count + 1)

    def test_live_currency_update_xe_com(self):
        self.test_company.currency_provider = 'xe_com'
        rates_count = len(self.currency_usd.rate_ids)
        res = self.test_company.update_currency_rates()
        self.assertTrue(res)
        self.assertEqual(len(self.currency_usd.rate_ids), rates_count + 1)

    def test_live_currency_update_bnr_com(self):
        self.test_company.currency_provider = 'bnr'
        rates_count = len(self.currency_usd.rate_ids)
        res = self.test_company.update_currency_rates()
        self.assertTrue(res)
        self.assertEqual(len(self.currency_usd.rate_ids), rates_count + 1)

    def test_live_currency_update_srb(self):
        self.test_company.currency_provider = 'srb'
        rates_count = len(self.currency_us_rate_ids)
        res = self.test_company.update_currency_rates()
        self.assertTrue(res)
        self.assertEqual(len(self.currency_usd.rate_ids), rates_count + 1)

    def test_live_currency_update_cbuae(self):
        self.test_company.currency_provider = 'cbuae'
        rates_count = len(self.currency_usd.rate_ids)
        res = self.test_company.update_currency_rates()
        self.assertTrue(res)
        self.assertEqual(len(self.currency_usd.rate_ids), rates_count + 1)

    def test_live_currency_update_cbegy(self):
        self.test_company.currency_provider = 'cbegy'
        rates_count = len(self.currency_usd.rate_ids)
        res = self.test_company.update_currency_rates()
        self.assertTrue(res)
        self.assertEqual(len(self.currency_usd.rate_ids), rates_count + 1)

    def test_live_currency_update_hmrc(self):
        self.test_company.currency_provider = 'hmrc'
        rates_count = len(self.currency_usd.rate_ids)
        res = self.test_company.update_currency_rates()
        self.assertTrue(res)
        self.assertEqual(len(self.currency_usd.rate_ids), rates_count + 1)

    def test_live_currency_update_bbr(self):
        self.test_company.currency_provider = 'bbr'
        rates_count = len(self.currency_usd.rate_ids)
        res = self.test_company.update_currency_rates()
        self.assertTrue(res)
        self.assertEqual(len(self.currency_usd.rate_ids), rates_count + 1)

    def test_live_currency_update_bcrp(self):
        pen = self.env.ref('base.PEN')
        pen.active = True
        usd = self.env.ref('base.USD')
        usd.active = True
        self.test_company.write({
            'currency_provider': 'bcrp',
            'currency_id': pen.id
        })
        Rate = self.env['res.currency.rate']
        pen_domain = [('currency_id', '=', pen.id), ('company_id', '=', self.test_company.id)]
        usd_domain = [('currency_id', '=', usd.id), ('company_id', '=', self.test_company.id)]
        pen_rates_count = Rate.search_count(pen_domain)
        usd_rates_count = Rate.search_count(usd_domain)

        self.assertTrue(self.test_company.update_currency_rates())

        self.assertEqual(Rate.search_count(pen_domain), pen_rates_count + 1)
        self.assertEqual(Rate.search_count(usd_domain), usd_rates_count + 1)

        lima_today = fields.Date.context_today(self.test_company.with_context(tz='America/Lima'))
        pen_rate = Rate.search(pen_domain, order='name desc', limit=1)
        usd_rate = Rate.search(usd_domain, order='name desc', limit=1)

        self.assertEqual(pen_rate.rate, 1.0)
        self.assertLess(usd_rate.rate, 1)

        self.assertLess(pen_rate.name, lima_today)
        # The publication of day D is stored on D - 1 so that it is the rate effective on D; it can be older when SUNAT has not published today.
        self.assertEqual(pen_rate.name, usd_rate.name)

    def test_live_currency_update_banguat(self):
        gtq = self.env.ref('base.GTQ')
        gtq.active = True
        usd = self.env.ref('base.USD')
        usd.active = True
        self.test_company.write({
            'currency_provider': 'banguat',
            'currency_id': gtq.id
        })
        gtq_rates_count = len(gtq.rate_ids)
        usd_rates_count = len(usd.rate_ids)
        res = self.test_company.update_currency_rates()
        self.assertTrue(res)
        self.assertEqual(len(gtq.rate_ids), gtq_rates_count + 1)
        self.assertEqual(gtq.rate_ids[-1].rate, 1.0)
        self.assertEqual(len(usd.rate_ids), usd_rates_count + 1)
        self.assertLess(usd.rate_ids[-1].rate, 1)

    def test_live_currency_update_tcmb(self):
        ytl = self.env.ref('base.TRY')
        ytl.active = True
        self.test_company.write({
            'currency_provider': 'tcmb',
            'currency_id': ytl.id
        })
        rates_count = len(ytl.rate_ids)
        res = self.test_company.update_currency_rates()
        self.assertTrue(res)
        self.assertEqual(len(ytl.rate_ids), rates_count + 1)

    def test_live_currency_update_nbp(self):
        pln = self.env.ref('base.PLN')
        pln.active = True
        usd = self.env.ref('base.USD')
        usd.active = True
        self.test_company.write({
            'currency_provider': 'nbp',
            'currency_id': pln.id
        })
        pln_rates_count = len(pln.rate_ids)
        usd_rates_count = len(usd.rate_ids)
        res = self.test_company.update_currency_rates()
        self.assertTrue(res)
        self.assertEqual(len(pln.rate_ids), pln_rates_count + 1)
        self.assertEqual(pln.rate_ids[-1].rate, 1.0)
        self.assertEqual(len(usd.rate_ids), usd_rates_count + 1)

    def test_live_currency_update_bnb(self):
        self.test_company.currency_provider = 'bnb'
        usd_rates_count = len(self.currency_usd.rate_ids)
        res = self.test_company.update_currency_rates()
        self.assertTrue(res)
        self.assertEqual(len(self.currency_usd.rate_ids), usd_rates_count + 1)

    def test_live_currency_update_bnm(self):
        myr = self.env.ref('base.MYR')
        myr.active = True
        usd = self.env.ref('base.USD')
        usd.active = True
        self.test_company.write({
            'currency_provider': 'bnm',
            'currency_id': myr.id
        })
        myr_rates_count = len(myr.rate_ids)
        usd_rates_count = len(usd.rate_ids)
        res = self.test_company.update_currency_rates()
        self.assertTrue(res)
        self.assertEqual(len(myr.rate_ids), myr_rates_count + 1)
        self.assertEqual(myr.rate_ids[-1].rate, 1.0)
        self.assertEqual(len(usd.rate_ids), usd_rates_count + 1)

    def test_live_currency_update_bot(self):
        self.test_company.currency_provider = 'bot'
        self.env.ref('base.THB').write({'active': True})
        rates_count = len(self.currency_usd.rate_ids)
        res = self.test_company.update_currency_rates()
        self.assertTrue(res)
        self.assertEqual(len(self.currency_usd.rate_ids), rates_count + 1)

    def test_live_currency_update_mnb(self):
        huf = self.env.ref('base.HUF')
        huf.active = True
        usd = self.env.ref('base.USD')
        usd.active = True
        self.test_company.write({
            'currency_provider': 'mnb',
            'currency_id': huf.id
        })
        huf_rates_count = len(huf.rate_ids)
        usd_rates_count = len(usd.rate_ids)
        res = self.test_company.update_currency_rates()
        self.assertTrue(res)
        self.assertEqual(len(huf.rate_ids), huf_rates_count + 1)
        self.assertEqual(huf.rate_ids[-1].rate, 1.0)
        self.assertEqual(len(usd.rate_ids), usd_rates_count + 1)

    def test_live_currency_update_bsi(self):
        """Test currency rate update from Bank of Slovenia (BSI)"""
        eur = self.env.ref('base.EUR')
        eur.active = True
        usd = self.env.ref('base.USD')
        usd.active = True
        self.test_company.write({
            'currency_provider': 'bsi',
            'currency_id': eur.id
        })
        eur_rates_count = len(eur.rate_ids)
        usd_rates_count = len(self.currency_usd.rate_ids)
        res = self.test_company.update_currency_rates()
        self.assertTrue(res)
        self.assertEqual(len(eur.rate_ids), eur_rates_count + 1)
        self.assertEqual(eur.rate_ids[-1].rate, 1.0)
        self.assertEqual(len(usd.rate_ids), usd_rates_count + 1)

    def test_live_currency_update_nbkz(self):
        self.test_company.currency_provider = 'nbkz'
        rates_count = len(self.currency_usd.rate_ids)
        res = self.test_company.update_currency_rates()
        self.assertTrue(res)
        self.assertEqual(len(self.currency_usd.rate_ids), rates_count + 1)

    def test_live_currency_update_cbu(self):
        eur = self.env.ref('base.EUR')
        eur.active = True
        usd = self.env.ref('base.USD')
        usd.active = True
        self.test_company.write({
            'currency_provider': 'cbu',
            'currency_id': eur.id,
        })
        eur_rates_count = len(eur.rate_ids)
        usd_rates_count = len(self.currency_usd.rate_ids)
        res = self.test_company.update_currency_rates()
        self.assertTrue(res)
        self.assertEqual(len(eur.rate_ids), eur_rates_count + 1)
        self.assertEqual(eur.rate_ids[-1].rate, 1.0)
        self.assertEqual(len(usd.rate_ids), usd_rates_count + 1)

    def test_live_currency_update_nbg(self):
        gel = self.env.ref('base.GEL')
        gel.active = True
        usd = self.env.ref('base.USD')
        usd.active = True
        self.test_company.write({
            'currency_provider': 'nbg',
            'currency_id': gel.id,
        })
        gel_rates_count = len(gel.rate_ids)
        usd_rates_count = len(usd.rate_ids)
        res = self.test_company.update_currency_rates()
        self.assertTrue(res)
        self.assertEqual(len(gel.rate_ids), gel_rates_count + 1)
        self.assertEqual(gel.rate_ids[-1].rate, 1.0)
        self.assertEqual(len(usd.rate_ids), usd_rates_count + 1)

    def test_live_currency_update_cbar(self):
        azn = self.env.ref('base.AZN')
        azn.active = True
        usd = self.env.ref('base.USD')
        usd.active = True
        self.test_company.write({
            'currency_provider': 'cbar',
            'currency_id': azn.id,
        })
        azn_rates_count = len(azn.rate_ids)
        usd_rates_count = len(usd.rate_ids)
        res = self.test_company.update_currency_rates()
        self.assertTrue(res)
        self.assertEqual(len(azn.rate_ids), azn_rates_count + 1)
        self.assertEqual(azn.rate_ids[-1].rate, 1.0)
        self.assertEqual(len(usd.rate_ids), usd_rates_count + 1)

    def test_live_currency_update_sama(self):
        sar = self.env.ref('base.SAR')
        sar.active = True
        usd = self.env.ref('base.USD')
        usd.active = True
        self.test_company.write({
            'currency_provider': 'sama',
            'currency_id': sar.id,
        })
        sar_rates_count = len(sar.rate_ids)
        usd_rates_count = len(usd.rate_ids)
        res = self.test_company.update_currency_rates()
        self.assertTrue(res)
        self.assertEqual(len(sar.rate_ids), sar_rates_count + 1)
        self.assertEqual(sar.rate_ids[-1].rate, 1.0)
        self.assertEqual(len(usd.rate_ids), usd_rates_count + 1)
