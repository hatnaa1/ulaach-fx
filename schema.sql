-- PostgreSQL schema for ulaach-fx (mnb_rates & bank_rates)

CREATE TABLE IF NOT EXISTS public.mnb_rates (
    rate_date date NOT NULL,
    code text NOT NULL,
    rate numeric(20,8),
    fetched_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT mnb_rates_pkey PRIMARY KEY (rate_date, code)
);

CREATE TABLE IF NOT EXISTS public.bank_rates (
    bank text NOT NULL,
    code text NOT NULL,
    rate_hour timestamp with time zone NOT NULL,
    name text,
    mongol_bank numeric(20,8),
    non_cash_buy numeric(20,8),
    non_cash_sell numeric(20,8),
    cash_buy numeric(20,8),
    cash_sell numeric(20,8),
    fetched_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT bank_rates_pkey PRIMARY KEY (bank, code, rate_hour)
);

CREATE INDEX IF NOT EXISTS bank_rates_code_hour_idx
    ON public.bank_rates USING btree (code, rate_hour DESC);
