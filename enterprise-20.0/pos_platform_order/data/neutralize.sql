UPDATE platform_order_provider
   SET state = 'disabled'
 WHERE state NOT IN ('test', 'disabled');
