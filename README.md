# zd-n8n-relay

** An application server to bypass n8n VPC while sending data from zendesk**

This server is configured with a Relay token and basic authentication. Zendesk webhook are notified when a certain trigger conditions are met and will transfer data to this server. This server will inturn post the webhook data to n8n webhook to trigger the corresponding workflow.