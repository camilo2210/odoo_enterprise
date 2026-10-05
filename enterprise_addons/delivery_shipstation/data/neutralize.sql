-- disable shipstation
UPDATE delivery_carrier
   SET shipstation_production_api_key = 'dummy'
 WHERE delivery_type = 'shipstation';
