from odoo.tests import tagged
from odoo.addons.l10n_ro_saft.tests.test_ro_saft_report_assets import TestRoSaftReportAssets


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestRoStockWarehouse(TestRoSaftReportAssets):
    """
    Test class for Romanian-specific warehouse configuration and logistics.
    Ensures that picking types and return flows are correctly automated.
    """
    _test_user_groups = None  # FIXME list needed groups

    def test_ro_warehouse_return_types_lifecycle(self):
        """
        Test the lifecycle of Romanian-specific return picking types:
        1. Automatic creation upon warehouse creation.
        2. Idempotence: switching delivery steps shouldn't create duplicates.
        3. Resilience: missing links should be repaired on update.
        4. Recovery: incorrect sequence codes should trigger re-creation.

        Note: Changes to 'delivery_steps' are used as a trigger to force the
        re-execution of '_create_or_update_sequences_and_picking_types'
        """
        warehouse = self.env['stock.warehouse'].create({
            'name': 'RO Warehouse',
            'code': 'ROWH',
            'company_id': self.env.company.id,
        })

        outgoing_return = warehouse.in_type_id.return_picking_type_id
        incoming_return = warehouse.out_type_id.return_picking_type_id
        self.assertRecordValues(outgoing_return, [
            {'sequence_code': 'INR', 'code': 'outgoing', 'return_picking_type_id': warehouse.in_type_id.id}
        ])
        self.assertRecordValues(incoming_return, [
            {'sequence_code': 'OUTR', 'code': 'incoming', 'return_picking_type_id': warehouse.out_type_id.id}
        ])

        warehouse.delivery_steps = 'pick_ship'
        self.assertRecordValues(warehouse.in_type_id.return_picking_type_id, [
            {'id': outgoing_return.id, 'sequence_code': 'INR', 'code': 'outgoing', 'return_picking_type_id': warehouse.in_type_id.id}
        ])
        self.assertRecordValues(warehouse.out_type_id.return_picking_type_id, [
            {'id': incoming_return.id, 'sequence_code': 'OUTR', 'code': 'incoming', 'return_picking_type_id': warehouse.out_type_id.id}
        ])

        warehouse.in_type_id.return_picking_type_id = False
        warehouse.out_type_id.return_picking_type_id = False
        warehouse.delivery_steps = 'pick_pack_ship'
        self.assertRecordValues(warehouse.in_type_id.return_picking_type_id, [
            {'id': outgoing_return.id, 'sequence_code': 'INR', 'code': 'outgoing', 'return_picking_type_id': warehouse.in_type_id.id}
        ])
        self.assertRecordValues(warehouse.out_type_id.return_picking_type_id, [
            {'id': incoming_return.id, 'sequence_code': 'OUTR', 'code': 'incoming', 'return_picking_type_id': warehouse.out_type_id.id}
        ])

        outgoing_return.sequence_code = 'NINR'
        incoming_return.sequence_code = 'NOUTR'
        warehouse.delivery_steps = 'ship_only'
        self.assertRecordValues(warehouse.in_type_id.return_picking_type_id, [
            {'sequence_code': 'INR', 'code': 'outgoing', 'return_picking_type_id': warehouse.in_type_id.id}
        ])
        self.assertNotEqual(outgoing_return.id, warehouse.in_type_id.return_picking_type_id.id)
        self.assertRecordValues(warehouse.out_type_id.return_picking_type_id, [
            {'sequence_code': 'OUTR', 'code': 'incoming', 'return_picking_type_id': warehouse.out_type_id.id}
        ])
        self.assertNotEqual(incoming_return.id, warehouse.out_type_id.return_picking_type_id.id)
