-- RADIX Talent Match Phase 1 schema foundation.
-- No official JDs, resumes, company benchmarks, aliases, or related-skill rows are seeded.

create or replace function public.radix_valid_company_levels(levels jsonb)
returns boolean
language plpgsql
immutable
as $$
declare
  category_codes constant text[] := array[
    'COD', 'DSA', 'OOD', 'APTI', 'COMM', 'AI',
    'CLOUD', 'SQL', 'SWE', 'SYSD', 'NETW', 'OS'
  ];
  entry record;
  level_value numeric;
  level_count integer;
begin
  if jsonb_typeof(levels) <> 'object'
     or not (levels ?& category_codes) then
    return false;
  end if;

  select count(*)::integer into level_count from jsonb_object_keys(levels);
  if level_count <> cardinality(category_codes) then
    return false;
  end if;

  for entry in select key, value from jsonb_each(levels)
  loop
    if not (entry.key = any(category_codes))
       or jsonb_typeof(entry.value) <> 'number' then
      return false;
    end if;

    level_value := (entry.value #>> '{}')::numeric;
    if level_value < 1 or level_value > 10 or level_value <> trunc(level_value) then
      return false;
    end if;
  end loop;

  return true;
end;
$$;

create table public.candidate_profiles (
  user_id uuid primary key references auth.users(id) on delete cascade,
  name text not null,
  email text not null,
  education text not null default '',
  skills jsonb not null default '[]'::jsonb,
  hackathons jsonb not null default '[]'::jsonb,
  internships jsonb not null default '[]'::jsonb,
  certifications jsonb not null default '[]'::jsonb,
  preferred_roles jsonb not null default '[]'::jsonb,
  cv_file text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint candidate_profiles_skills_array check (jsonb_typeof(skills) = 'array'),
  constraint candidate_profiles_hackathons_array check (jsonb_typeof(hackathons) = 'array'),
  constraint candidate_profiles_internships_array check (jsonb_typeof(internships) = 'array'),
  constraint candidate_profiles_certifications_array check (jsonb_typeof(certifications) = 'array'),
  constraint candidate_profiles_preferred_roles_array check (jsonb_typeof(preferred_roles) = 'array')
);

create table public.documents (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  source_type text not null check (source_type in ('jd', 'resume')),
  original_filename text not null,
  content_type text not null,
  byte_size bigint not null check (byte_size > 0),
  checksum_sha256 text,
  storage_path text not null unique,
  extraction_status text not null default 'pending'
    check (extraction_status in ('pending', 'processing', 'draft', 'reviewed', 'failed')),
  extraction jsonb not null default '{}'::jsonb,
  reviewed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (id, owner_id),
  constraint documents_storage_path_owned check (storage_path like owner_id::text || '/%'),
  constraint documents_extraction_object check (jsonb_typeof(extraction) = 'object')
);

create index documents_owner_created_idx on public.documents (owner_id, created_at desc);

create table public.job_descriptions (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  document_id uuid not null,
  company text,
  role text,
  location text,
  extraction jsonb not null default '{}'::jsonb,
  reviewed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (id, owner_id),
  foreign key (document_id, owner_id)
    references public.documents (id, owner_id) on delete cascade,
  constraint job_descriptions_extraction_object check (jsonb_typeof(extraction) = 'object')
);

create index job_descriptions_owner_created_idx on public.job_descriptions (owner_id, created_at desc);

create table public.company_benchmarks (
  id uuid primary key default gen_random_uuid(),
  company text not null,
  expected_levels jsonb not null,
  source_kind text not null check (source_kind in ('official', 'demo')),
  source_reference text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint company_benchmarks_levels_valid check (public.radix_valid_company_levels(expected_levels))
);

create index company_benchmarks_company_idx on public.company_benchmarks (company);

create table public.analysis_runs (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  analysis_kind text not null check (analysis_kind in ('talent_check', 'skill_match')),
  profile_user_id uuid not null,
  job_description_id uuid,
  benchmark_id uuid references public.company_benchmarks(id) on delete restrict,
  result_status text not null check (result_status in ('completed', 'not_scored', 'unavailable', 'failed')),
  input_payload jsonb not null default '{}'::jsonb,
  result_payload jsonb not null default '{}'::jsonb,
  scoring_version text,
  normalization_version text,
  created_at timestamptz not null default now(),
  unique (id, owner_id),
  foreign key (profile_user_id) references public.candidate_profiles(user_id) on delete cascade,
  foreign key (job_description_id, owner_id)
    references public.job_descriptions (id, owner_id) on delete cascade,
  constraint analysis_runs_input_object check (jsonb_typeof(input_payload) = 'object'),
  constraint analysis_runs_result_object check (jsonb_typeof(result_payload) = 'object'),
  constraint analysis_runs_kind_reference check (
    (analysis_kind = 'talent_check' and job_description_id is null
      and (benchmark_id is not null or result_status in ('not_scored', 'unavailable', 'failed')))
    or (analysis_kind = 'skill_match' and job_description_id is not null and benchmark_id is null)
  )
);

create index analysis_runs_owner_created_idx on public.analysis_runs (owner_id, created_at desc);

create table public.skill_aliases (
  id uuid primary key default gen_random_uuid(),
  category_code text not null check (category_code in (
    'COD', 'DSA', 'OOD', 'APTI', 'COMM', 'AI', 'CLOUD', 'SQL', 'SWE', 'SYSD', 'NETW', 'OS', 'OTHER'
  )),
  normalized_alias text not null,
  canonical_skill text not null,
  config_version text not null,
  created_at timestamptz not null default now(),
  unique (category_code, normalized_alias)
);

create table public.related_skill_edges (
  id uuid primary key default gen_random_uuid(),
  category_code text not null check (category_code in (
    'COD', 'DSA', 'OOD', 'APTI', 'COMM', 'AI', 'CLOUD', 'SQL', 'SWE', 'SYSD', 'NETW', 'OS', 'OTHER'
  )),
  source_skill text not null,
  related_skill text not null,
  config_version text not null,
  created_at timestamptz not null default now(),
  unique (category_code, source_skill, related_skill),
  check (source_skill <> related_skill)
);

-- Owner-scoped RLS for candidate data.
alter table public.candidate_profiles enable row level security;
alter table public.documents enable row level security;
alter table public.job_descriptions enable row level security;
alter table public.analysis_runs enable row level security;

create policy candidate_profiles_owner_all on public.candidate_profiles
  for all to authenticated
  using (user_id = (select auth.uid()))
  with check (user_id = (select auth.uid()));

create policy documents_owner_all on public.documents
  for all to authenticated
  using (owner_id = (select auth.uid()))
  with check (owner_id = (select auth.uid()));

create policy job_descriptions_owner_all on public.job_descriptions
  for all to authenticated
  using (owner_id = (select auth.uid()))
  with check (owner_id = (select auth.uid()));

create policy analysis_runs_owner_all on public.analysis_runs
  for all to authenticated
  using (
    owner_id = (select auth.uid())
    and profile_user_id = (select auth.uid())
  )
  with check (
    owner_id = (select auth.uid())
    and profile_user_id = (select auth.uid())
  );

-- Reference/configuration data is readable by authenticated users, but has no client write policy.
alter table public.company_benchmarks enable row level security;
alter table public.skill_aliases enable row level security;
alter table public.related_skill_edges enable row level security;

create policy company_benchmarks_authenticated_read on public.company_benchmarks
  for select to authenticated using (true);

create policy skill_aliases_authenticated_read on public.skill_aliases
  for select to authenticated using (true);

create policy related_skill_edges_authenticated_read on public.related_skill_edges
  for select to authenticated using (true);

grant select, insert, update, delete on public.candidate_profiles to authenticated;
grant select, insert, update, delete on public.documents to authenticated;
grant select, insert, update, delete on public.job_descriptions to authenticated;
grant select, insert, update, delete on public.analysis_runs to authenticated;
grant select on public.company_benchmarks to authenticated;
grant select on public.skill_aliases to authenticated;
grant select on public.related_skill_edges to authenticated;

-- Private file storage. Expected object path: <auth.uid>/<document UUID>/<filename>.
insert into storage.buckets (id, name, public)
values ('radix-private-documents', 'radix-private-documents', false)
on conflict (id) do update set public = false;

create policy radix_documents_owner_select on storage.objects
  for select to authenticated
  using (
    bucket_id = 'radix-private-documents'
    and (storage.foldername(name))[1] = (select auth.uid())::text
  );

create policy radix_documents_owner_insert on storage.objects
  for insert to authenticated
  with check (
    bucket_id = 'radix-private-documents'
    and (storage.foldername(name))[1] = (select auth.uid())::text
  );

create policy radix_documents_owner_update on storage.objects
  for update to authenticated
  using (
    bucket_id = 'radix-private-documents'
    and (storage.foldername(name))[1] = (select auth.uid())::text
  )
  with check (
    bucket_id = 'radix-private-documents'
    and (storage.foldername(name))[1] = (select auth.uid())::text
  );

create policy radix_documents_owner_delete on storage.objects
  for delete to authenticated
  using (
    bucket_id = 'radix-private-documents'
    and (storage.foldername(name))[1] = (select auth.uid())::text
  );
