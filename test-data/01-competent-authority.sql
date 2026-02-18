-- Insert competent authorities
-- These must be inserted first as area references them via foreign key
-- Can be removed once "competent authorities submit areas" is also supported (as this will provision the competent authorities automatically)

-- Gemeente Amsterdam
INSERT INTO competent_authority (competent_authority_id, competent_authority_name, created_at)
VALUES (
  'sdep-ca0363',
  'Amsterdam (inclusief Weesp)',
  '2025-01-01 00:00:00+00'::timestamptz
) ON CONFLICT (competent_authority_id, created_at) DO NOTHING;

-- Gemeente Rotterdam
INSERT INTO competent_authority (competent_authority_id, competent_authority_name, created_at)
VALUES (
  'sdep-ca0599',
  'Rotterdam',
  '2025-01-01 00:00:00+00'::timestamptz
) ON CONFLICT (competent_authority_id, created_at) DO NOTHING;

-- Gemeente Den Haag
INSERT INTO competent_authority (competent_authority_id, competent_authority_name, created_at)
VALUES (
  'sdep-ca0518',
  'Den Haag',
  '2025-01-01 00:00:00+00'::timestamptz
) ON CONFLICT (competent_authority_id, created_at) DO NOTHING;

-- Gemeente Amstelveen
INSERT INTO competent_authority (competent_authority_id, competent_authority_name, created_at)
VALUES (
  'sdep-ca0362',
  'Amstelveen',
  '2025-01-01 00:00:00+00'::timestamptz
) ON CONFLICT (competent_authority_id, created_at) DO NOTHING;

-- Gemeente Bergen (Noord-Holland)
INSERT INTO competent_authority (competent_authority_id, competent_authority_name, created_at)
VALUES (
  'sdep-ca0373',
  'Bergen (Noord-Holland)',
  '2025-01-01 00:00:00+00'::timestamptz
) ON CONFLICT (competent_authority_id, created_at) DO NOTHING;

-- Gemeente Delft
INSERT INTO competent_authority (competent_authority_id, competent_authority_name, created_at)
VALUES (
  'sdep-ca0503',
  'Delft',
  '2025-01-01 00:00:00+00'::timestamptz
) ON CONFLICT (competent_authority_id, created_at) DO NOTHING;

-- Gemeente Diemen
INSERT INTO competent_authority (competent_authority_id, competent_authority_name, created_at)
VALUES (
  'sdep-ca0384',
  'Diemen',
  '2025-01-01 00:00:00+00'::timestamptz
) ON CONFLICT (competent_authority_id, created_at) DO NOTHING;

-- Gemeente Gouda
INSERT INTO competent_authority (competent_authority_id, competent_authority_name, created_at)
VALUES (
  'sdep-ca0513',
  'Gouda',
  '2025-01-01 00:00:00+00'::timestamptz
) ON CONFLICT (competent_authority_id, created_at) DO NOTHING;

-- Gemeente Groningen
INSERT INTO competent_authority (competent_authority_id, competent_authority_name, created_at)
VALUES (
  'sdep-ca0014',
  'Groningen (inclusief Haren, Slochteren en Ten Boer)',
  '2025-01-01 00:00:00+00'::timestamptz
) ON CONFLICT (competent_authority_id, created_at) DO NOTHING;

-- Gemeente Haarlem
INSERT INTO competent_authority (competent_authority_id, competent_authority_name, created_at)
VALUES (
  'sdep-ca0392',
  'Haarlem',
  '2025-01-01 00:00:00+00'::timestamptz
) ON CONFLICT (competent_authority_id, created_at) DO NOTHING;

-- Gemeente Katwijk
INSERT INTO competent_authority (competent_authority_id, competent_authority_name, created_at)
VALUES (
  'sdep-ca0537',
  'Katwijk',
  '2025-01-01 00:00:00+00'::timestamptz
) ON CONFLICT (competent_authority_id, created_at) DO NOTHING;

-- Gemeente Landsmeer
INSERT INTO competent_authority (competent_authority_id, competent_authority_name, created_at)
VALUES (
  'sdep-ca0415',
  'Landsmeer',
  '2025-01-01 00:00:00+00'::timestamptz
) ON CONFLICT (competent_authority_id, created_at) DO NOTHING;

-- Gemeente Leiden
INSERT INTO competent_authority (competent_authority_id, competent_authority_name, created_at)
VALUES (
  'sdep-ca0546',
  'Leiden',
  '2025-01-01 00:00:00+00'::timestamptz
) ON CONFLICT (competent_authority_id, created_at) DO NOTHING;

-- Gemeente Maastricht
INSERT INTO competent_authority (competent_authority_id, competent_authority_name, created_at)
VALUES (
  'sdep-ca0935',
  'Maastricht',
  '2025-01-01 00:00:00+00'::timestamptz
) ON CONFLICT (competent_authority_id, created_at) DO NOTHING;

-- Gemeente Middelburg
INSERT INTO competent_authority (competent_authority_id, competent_authority_name, created_at)
VALUES (
  'sdep-ca0687',
  'Middelburg',
  '2025-01-01 00:00:00+00'::timestamptz
) ON CONFLICT (competent_authority_id, created_at) DO NOTHING;

-- Gemeente Noordwijk
INSERT INTO competent_authority (competent_authority_id, competent_authority_name, created_at)
VALUES (
  'sdep-ca0575',
  'Noordwijk (inclusief Noordwijkerhout)',
  '2025-01-01 00:00:00+00'::timestamptz
) ON CONFLICT (competent_authority_id, created_at) DO NOTHING;

-- Gemeente Pijnacker-Nootdorp
INSERT INTO competent_authority (competent_authority_id, competent_authority_name, created_at)
VALUES (
  'sdep-ca1926',
  'Pijnacker-Nootdorp',
  '2025-01-01 00:00:00+00'::timestamptz
) ON CONFLICT (competent_authority_id, created_at) DO NOTHING;

-- Gemeente Renkum
INSERT INTO competent_authority (competent_authority_id, competent_authority_name, created_at)
VALUES (
  'sdep-ca0274',
  'Renkum',
  '2025-01-01 00:00:00+00'::timestamptz
) ON CONFLICT (competent_authority_id, created_at) DO NOTHING;

-- Gemeente Sluis
INSERT INTO competent_authority (competent_authority_id, competent_authority_name, created_at)
VALUES (
  'sdep-ca1714',
  'Sluis',
  '2025-01-01 00:00:00+00'::timestamptz
) ON CONFLICT (competent_authority_id, created_at) DO NOTHING;

-- Gemeente Schouwen-Duiveland
INSERT INTO competent_authority (competent_authority_id, competent_authority_name, created_at)
VALUES (
  'sdep-ca1676',
  'Schouwen-Duiveland',
  '2025-01-01 00:00:00+00'::timestamptz
) ON CONFLICT (competent_authority_id, created_at) DO NOTHING;

-- Gemeente Texel
INSERT INTO competent_authority (competent_authority_id, competent_authority_name, created_at)
VALUES (
  'sdep-ca0448',
  'Texel',
  '2025-01-01 00:00:00+00'::timestamptz
) ON CONFLICT (competent_authority_id, created_at) DO NOTHING;

-- Gemeente Utrecht
INSERT INTO competent_authority (competent_authority_id, competent_authority_name, created_at)
VALUES (
  'sdep-ca0344',
  'Utrecht',
  '2025-01-01 00:00:00+00'::timestamptz
) ON CONFLICT (competent_authority_id, created_at) DO NOTHING;

-- Gemeente Vlissingen
INSERT INTO competent_authority (competent_authority_id, competent_authority_name, created_at)
VALUES (
  'sdep-ca0718',
  'Vlissingen',
  '2025-01-01 00:00:00+00'::timestamptz
) ON CONFLICT (competent_authority_id, created_at) DO NOTHING;

-- Gemeente Voorschoten
INSERT INTO competent_authority (competent_authority_id, competent_authority_name, created_at)
VALUES (
  'sdep-ca0626',
  'Voorschoten',
  '2025-01-01 00:00:00+00'::timestamptz
) ON CONFLICT (competent_authority_id, created_at) DO NOTHING;

-- Gemeente Waterland
INSERT INTO competent_authority (competent_authority_id, competent_authority_name, created_at)
VALUES (
  'sdep-ca0852',
  'Waterland',
  '2025-01-01 00:00:00+00'::timestamptz
) ON CONFLICT (competent_authority_id, created_at) DO NOTHING;

-- Gemeente Zaanstad
INSERT INTO competent_authority (competent_authority_id, competent_authority_name, created_at)
VALUES (
  'sdep-ca0479',
  'Zaanstad',
  '2025-01-01 00:00:00+00'::timestamptz
) ON CONFLICT (competent_authority_id, created_at) DO NOTHING;

-- Gemeente Zandvoort
INSERT INTO competent_authority (competent_authority_id, competent_authority_name, created_at)
VALUES (
  'sdep-ca0473',
  'Zandvoort',
  '2025-01-01 00:00:00+00'::timestamptz
) ON CONFLICT (competent_authority_id, created_at) DO NOTHING;

-- Gemeente Zwolle
INSERT INTO competent_authority (competent_authority_id, competent_authority_name, created_at)
VALUES (
  'sdep-ca0193',
  'Zwolle',
  '2025-01-01 00:00:00+00'::timestamptz
) ON CONFLICT (competent_authority_id, created_at) DO NOTHING;
