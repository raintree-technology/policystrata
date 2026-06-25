drop table if exists ticket_events;
drop table if exists support_tickets;
drop table if exists invoices;
drop table if exists subscriptions;
drop table if exists agents;
drop table if exists accounts;
drop table if exists tenants;

do $$
begin
  create role policystrata_app login password 'policystrata_app';
exception
  when duplicate_object or unique_violation then
    alter role policystrata_app with login password 'policystrata_app';
end
$$;

create table tenants (
  id text primary key,
  name text not null
);

create table accounts (
  id serial primary key,
  tenant_id text not null references tenants(id),
  legacy_tenant_id text,
  name text not null,
  region text not null,
  customer_email text not null
);

create table subscriptions (
  id serial primary key,
  account_id integer not null references accounts(id),
  plan text not null,
  status text not null
);

create table invoices (
  id serial primary key,
  subscription_id integer not null references subscriptions(id),
  invoice_date date not null,
  gross_amount_cents integer not null,
  net_amount_cents integer not null
);

create table agents (
  id serial primary key,
  tenant_id text not null references tenants(id),
  email text not null,
  name text not null
);

create table support_tickets (
  id serial primary key,
  account_id integer not null references accounts(id),
  assigned_agent_id integer references agents(id),
  severity text not null,
  escalated boolean not null default false,
  resolution_hours integer not null
);

create table ticket_events (
  id serial primary key,
  ticket_id integer not null references support_tickets(id),
  event_type text not null,
  created_at timestamptz not null
);

alter table accounts enable row level security;
alter table subscriptions enable row level security;
alter table invoices enable row level security;
alter table support_tickets enable row level security;
alter table ticket_events enable row level security;

alter table accounts force row level security;
alter table subscriptions force row level security;
alter table invoices force row level security;
alter table support_tickets force row level security;
alter table ticket_events force row level security;

create policy tenant_isolation_accounts on accounts
  using (tenant_id = current_setting('app.tenant_id', true));

create policy tenant_isolation_subscriptions on subscriptions
  using (exists (
    select 1 from accounts
    where accounts.id = subscriptions.account_id
      and accounts.tenant_id = current_setting('app.tenant_id', true)
  ));

create policy tenant_isolation_invoices on invoices
  using (exists (
    select 1 from subscriptions
    join accounts on accounts.id = subscriptions.account_id
    where subscriptions.id = invoices.subscription_id
      and accounts.tenant_id = current_setting('app.tenant_id', true)
  ));

create policy tenant_isolation_tickets on support_tickets
  using (exists (
    select 1 from accounts
    where accounts.id = support_tickets.account_id
      and accounts.tenant_id = current_setting('app.tenant_id', true)
  ));

create policy tenant_isolation_events on ticket_events
  using (exists (
    select 1 from support_tickets
    join accounts on accounts.id = support_tickets.account_id
    where support_tickets.id = ticket_events.ticket_id
      and accounts.tenant_id = current_setting('app.tenant_id', true)
  ));

grant usage on schema public to policystrata_app;
grant select on tenants to policystrata_app;
grant select on accounts to policystrata_app;
grant select on subscriptions to policystrata_app;
grant select on invoices to policystrata_app;
grant select on agents to policystrata_app;
grant select on support_tickets to policystrata_app;
grant select on ticket_events to policystrata_app;
