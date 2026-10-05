# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class PosConfig(models.Model):
    _inherit = 'pos.config'

    @api.model
    def load_onboarding_pos_urban_piper_demo(self, with_demo_data=True):
        """Enable UrbanPiper on main restaurant config and load demo orders."""
        restaurant_config = self.env.ref('pos_restaurant.pos_config_main_restaurant', raise_if_not_found=False)
        urbanpiper_store = self.env.ref('pos_urban_piper.pos_urbanpiper_demo_store', raise_if_not_found=False)
        if not (urbanpiper_store and not urbanpiper_store.config_id and restaurant_config):
            return

        urbanpiper_store.config_id = restaurant_config

        ubereats_id, doordash_id, justeat_id = self.get_record_by_ref([
            'pos_urban_piper.pos_delivery_provider_ubereats',
            'pos_urban_piper.pos_delivery_provider_doordash',
            'pos_urban_piper.pos_delivery_provider_justeat',
        ])
        partner_ids = self.get_record_by_ref([
            'base.res_partner_address_7',
            'base.res_partner_address_31',
        ])
        products = list(map(
            self.env.ref,
            (
                'pos_restaurant.pos_food_chirashi',
                'pos_restaurant.pos_food_temaki',
                'pos_restaurant.coke',
            )
        ))
        product_tmpls = products[0].product_tmpl_id | products[1].product_tmpl_id | products[2].product_tmpl_id
        product_tmpls.urbanpiper_store_ids |= urbanpiper_store
        UrbanPiperTestOrder = self.env['pos.urbanpiper.test.order.wizard'].with_context(store_id=urbanpiper_store.id)

        # Demo order 1 - Placed
        order_1 = UrbanPiperTestOrder.create({
            'product_id': product_tmpls[0].id,
            'quantity': 7,
            'delivery_provider_id': ubereats_id,
            'delivery_instruction': 'Extra spicy please 🔥',
            'partner_id': partner_ids[0],
        }).make_test_order('1801701')

        # Demo order 2 - Acknowledged
        order_2 = UrbanPiperTestOrder.create({
            'product_id': product_tmpls[1].id,
            'quantity': 4,
            'delivery_provider_id': doordash_id,
            'delivery_instruction': 'No mushrooms — they look suspicious',
            'partner_id': partner_ids[1],
        }).make_test_order('2911025')
        order_2.process_urbanpiper_order_status_update({
            'order_id': '2911025',
            'new_state': 'Acknowledged',
            'store_id': 'demo',
        }, urbanpiper_store)
        self.env['pos.prep.order'].update_last_order_change(order_2)

        # Demo order 3 - Food Ready
        order_3 = UrbanPiperTestOrder.create({
            'product_id': product_tmpls[2].id,
            'quantity': 2,
            'delivery_provider_id': justeat_id,
            'delivery_instruction': ' ',
            'partner_id': partner_ids[0],
        }).make_test_order('0412257')
        order_3.process_urbanpiper_order_status_update({
            'order_id': '0412257',
            'new_state': 'Food Ready',
            'store_id': 'demo',
        }, urbanpiper_store)
        order_3.process_urbanpiper_rider_status({
            'delivery_info': {
                'delivery_person_details': {
                    'name': 'John Doe',
                    'phone': '+55 00 1234 4574',
                },
            },
            'order_id': '0412257',
            'store': {
                'ref_id': 'demo',
            },
        }, urbanpiper_store)
        self.env['pos.prep.order'].update_last_order_change(order_3)

        # Update Order ref xml-ids
        self.env['ir.model.data']._update_xmlids([
            {
                'xml_id': 'pos_self_order_urban_piper.demo_ubereats_order',
                'record': order_1,
                'noupdate': True,
            },
            {
                'xml_id': 'pos_self_order_urban_piper.demo_doordash_order',
                'record': order_2,
                'noupdate': True,
            },
            {
                'xml_id': 'pos_self_order_urban_piper.demo_justeat_order',
                'record': order_3,
                'noupdate': True,
            },
        ])
