insert into tenants (id, name) values
  ('acme', 'Acme Health'),
  ('beta', 'Beta Logistics');

insert into accounts (tenant_id, legacy_tenant_id, name, region, customer_email) values
  ('acme', 'old-acme', 'Acme West', 'west', 'buyer-west@acme.example'),
  ('acme', 'old-acme', 'Acme East', 'east', 'buyer-east@acme.example'),
  ('beta', 'old-beta', 'Beta North', 'north', 'ops@beta.example'),
  ('beta', 'old-beta', 'Beta South', 'south', 'finance@beta.example');

insert into subscriptions (account_id, plan, status) values
  (1, 'enterprise', 'active'),
  (2, 'pro', 'active'),
  (3, 'enterprise', 'active'),
  (4, 'starter', 'active');

insert into invoices (subscription_id, invoice_date, gross_amount_cents, net_amount_cents) values
  (1, '2026-05-12', 7000, 6000),
  (2, '2026-05-17', 5000, 4000),
  (3, '2026-05-18', 6000, 5000),
  (4, '2026-05-21', 3000, 3000),
  (1, '2026-04-29', 1000, 800);

insert into agents (tenant_id, email, name) values
  ('acme', 'agent-a@acme.example', 'Avery'),
  ('beta', 'agent-b@beta.example', 'Blair');

insert into support_tickets (account_id, assigned_agent_id, severity, escalated, resolution_hours) values
  (1, 1, 'high', true, 24),
  (1, 1, 'medium', false, 10),
  (2, 1, 'low', false, 6),
  (2, 1, 'high', true, 32),
  (3, 2, 'high', true, 18),
  (4, 2, 'medium', false, 12);

insert into ticket_events (ticket_id, event_type, created_at) values
  (1, 'created', '2026-05-01T08:00:00Z'),
  (1, 'comment', '2026-05-01T09:00:00Z'),
  (1, 'escalated', '2026-05-01T10:00:00Z'),
  (2, 'created', '2026-05-02T08:00:00Z'),
  (3, 'created', '2026-05-03T08:00:00Z'),
  (4, 'created', '2026-05-04T08:00:00Z'),
  (4, 'escalated', '2026-05-04T11:00:00Z'),
  (5, 'created', '2026-05-05T08:00:00Z'),
  (5, 'escalated', '2026-05-05T11:00:00Z'),
  (6, 'created', '2026-05-06T08:00:00Z');
