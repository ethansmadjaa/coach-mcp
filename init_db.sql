create table if not exists meals (
  id           bigserial primary key,
  eaten_at     timestamptz not null,
  description  text not null,
  kcal         numeric(7,1) not null,
  protein_g    numeric(6,1),
  carbs_g      numeric(6,1),
  fat_g        numeric(6,1),
  source       text not null check (source in ('estimated','exact')),
  created_at   timestamptz not null default now()
);

create table if not exists workouts (
  id           bigserial primary key,
  done_at      timestamptz not null,
  type         text not null,
  duration_min integer not null,
  kcal_burned  numeric(7,1) not null,
  source       text not null check (source in ('estimated','exact')),
  notes        text,
  created_at   timestamptz not null default now()
);

create table if not exists weights (
  id           bigserial primary key,
  measured_at  timestamptz not null,
  kg           numeric(5,2) not null,
  created_at   timestamptz not null default now()
);
