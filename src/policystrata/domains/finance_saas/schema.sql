create table advisors (
    id text primary key,
    firm_id text not null,
    name text not null,
    region text not null
);

create table households (
    id text primary key,
    firm_id text not null,
    legacy_firm_id text,
    advisor_id text not null references advisors(id),
    name text not null,
    tax_id text not null,
    segment text not null
);

create table accounts (
    id text primary key,
    household_id text not null references households(id),
    account_type text not null
);

create table transactions (
    id text primary key,
    account_id text not null references accounts(id),
    transaction_date date not null,
    transaction_type text not null,
    amount_cents integer not null,
    gross_amount_cents integer not null,
    fee_cents integer not null
);

create table balances (
    id text primary key,
    account_id text not null references accounts(id),
    balance_date date not null,
    market_value_cents integer not null
);

alter table advisors enable row level security;
alter table households enable row level security;
alter table accounts enable row level security;
alter table transactions enable row level security;
alter table balances enable row level security;

create policy firm_isolation_advisors on advisors
    using (firm_id = current_setting('policystrata.firm_id', true));

create policy firm_isolation_households on households
    using (firm_id = current_setting('policystrata.firm_id', true));

create policy firm_isolation_accounts on accounts
    using (
        exists (
            select 1
            from households
            where households.id = accounts.household_id
              and households.firm_id = current_setting('policystrata.firm_id', true)
        )
    );

create policy firm_isolation_transactions on transactions
    using (
        exists (
            select 1
            from accounts
            join households on households.id = accounts.household_id
            where accounts.id = transactions.account_id
              and households.firm_id = current_setting('policystrata.firm_id', true)
        )
    );

create policy firm_isolation_balances on balances
    using (
        exists (
            select 1
            from accounts
            join households on households.id = accounts.household_id
            where accounts.id = balances.account_id
              and households.firm_id = current_setting('policystrata.firm_id', true)
        )
    );
