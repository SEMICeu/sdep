-- Insert competent authorities
-- These must be inserted first as area references them via foreign key
-- Can be removed once "competent authorities submit areas" is also supported (as this will provision the competent authorities automatically)

-- Gemeente Amsterdam
INSERT INTO competent_authority (competent_authority_id, client_id, competent_authority_name, created_at)
VALUES (
  'c4ac8ccf-a281-5789-bad7-28dfac20ca7f',
  'sdep-ca.0363',
  'Amsterdam (inclusief Weesp)',
  '2025-01-01 00:00:00+00'::timestamptz
) ON CONFLICT (client_id, competent_authority_id, created_at) DO NOTHING;

-- Gemeente Rotterdam
INSERT INTO competent_authority (competent_authority_id, client_id, competent_authority_name, created_at)
VALUES (
  'a30df3a7-7e38-534c-b9c0-7666bad077d2',
  'sdep-ca.0599',
  'Rotterdam',
  '2025-01-01 00:00:00+00'::timestamptz
) ON CONFLICT (client_id, competent_authority_id, created_at) DO NOTHING;

-- Gemeente Den Haag
INSERT INTO competent_authority (competent_authority_id, client_id, competent_authority_name, created_at)
VALUES (
  '363ce948-b057-54f3-a916-5dd127a93986',
  'sdep-ca.0518',
  'Den Haag',
  '2025-01-01 00:00:00+00'::timestamptz
) ON CONFLICT (client_id, competent_authority_id, created_at) DO NOTHING;

-- Gemeente Amstelveen
INSERT INTO competent_authority (competent_authority_id, client_id, competent_authority_name, created_at)
VALUES (
  '05cd4276-7fb6-58f9-ba53-b4b8bb841800',
  'sdep-ca0362',
  'Amstelveen',
  '2025-01-01 00:00:00+00'::timestamptz
) ON CONFLICT (client_id, competent_authority_id, created_at) DO NOTHING;

-- Gemeente Bergen (Noord-Holland)
INSERT INTO competent_authority (competent_authority_id, client_id, competent_authority_name, created_at)
VALUES (
  '4c2cae62-415c-5e4f-8365-64867c97acd1',
  'sdep-ca0373',
  'Bergen (Noord-Holland)',
  '2025-01-01 00:00:00+00'::timestamptz
) ON CONFLICT (client_id, competent_authority_id, created_at) DO NOTHING;

-- Gemeente Delft
INSERT INTO competent_authority (competent_authority_id, client_id, competent_authority_name, created_at)
VALUES (
  'a296eb87-dcef-5edc-a173-f749bde80f11',
  'sdep-ca0503',
  'Delft',
  '2025-01-01 00:00:00+00'::timestamptz
) ON CONFLICT (client_id, competent_authority_id, created_at) DO NOTHING;

-- Gemeente Diemen
INSERT INTO competent_authority (competent_authority_id, client_id, competent_authority_name, created_at)
VALUES (
  '67fed8cf-b536-507e-8489-af4e1cb04ba5',
  'sdep-ca0384',
  'Diemen',
  '2025-01-01 00:00:00+00'::timestamptz
) ON CONFLICT (client_id, competent_authority_id, created_at) DO NOTHING;

-- Gemeente Gouda
INSERT INTO competent_authority (competent_authority_id, client_id, competent_authority_name, created_at)
VALUES (
  '843c21a2-10d0-51a7-81c7-510a7d265b6e',
  'sdep-ca0513',
  'Gouda',
  '2025-01-01 00:00:00+00'::timestamptz
) ON CONFLICT (client_id, competent_authority_id, created_at) DO NOTHING;

-- Gemeente Groningen
INSERT INTO competent_authority (competent_authority_id, client_id, competent_authority_name, created_at)
VALUES (
  '8c1f41c4-0d6f-516a-b626-89cea0370f15',
  'sdep-ca0014',
  'Groningen (inclusief Haren, Slochteren en Ten Boer)',
  '2025-01-01 00:00:00+00'::timestamptz
) ON CONFLICT (client_id, competent_authority_id, created_at) DO NOTHING;

-- Gemeente Haarlem
INSERT INTO competent_authority (competent_authority_id, client_id, competent_authority_name, created_at)
VALUES (
  '3d648d22-19f5-5c6f-bef3-d2ac6ad6d514',
  'sdep-ca0392',
  'Haarlem',
  '2025-01-01 00:00:00+00'::timestamptz
) ON CONFLICT (client_id, competent_authority_id, created_at) DO NOTHING;

-- Gemeente Katwijk
INSERT INTO competent_authority (competent_authority_id, client_id, competent_authority_name, created_at)
VALUES (
  '51658261-9835-5e57-8089-ff7b14097e5a',
  'sdep-ca0537',
  'Katwijk',
  '2025-01-01 00:00:00+00'::timestamptz
) ON CONFLICT (client_id, competent_authority_id, created_at) DO NOTHING;

-- Gemeente Landsmeer
INSERT INTO competent_authority (competent_authority_id, client_id, competent_authority_name, created_at)
VALUES (
  '2c43298f-c4f2-5dbf-b8dc-9506e4606fda',
  'sdep-ca0415',
  'Landsmeer',
  '2025-01-01 00:00:00+00'::timestamptz
) ON CONFLICT (client_id, competent_authority_id, created_at) DO NOTHING;

-- Gemeente Leiden
INSERT INTO competent_authority (competent_authority_id, client_id, competent_authority_name, created_at)
VALUES (
  '6499b306-44a4-5379-9a16-190acaa0475b',
  'sdep-ca0546',
  'Leiden',
  '2025-01-01 00:00:00+00'::timestamptz
) ON CONFLICT (client_id, competent_authority_id, created_at) DO NOTHING;

-- Gemeente Maastricht
INSERT INTO competent_authority (competent_authority_id, client_id, competent_authority_name, created_at)
VALUES (
  '6df9eba2-b88d-502e-8ae4-92ded9684460',
  'sdep-ca0935',
  'Maastricht',
  '2025-01-01 00:00:00+00'::timestamptz
) ON CONFLICT (client_id, competent_authority_id, created_at) DO NOTHING;

-- Gemeente Middelburg
INSERT INTO competent_authority (competent_authority_id, client_id, competent_authority_name, created_at)
VALUES (
  '3f9f0b48-a7de-5a8f-bb39-192970cc3478',
  'sdep-ca0687',
  'Middelburg',
  '2025-01-01 00:00:00+00'::timestamptz
) ON CONFLICT (client_id, competent_authority_id, created_at) DO NOTHING;

-- Gemeente Noordwijk
INSERT INTO competent_authority (competent_authority_id, client_id, competent_authority_name, created_at)
VALUES (
  'ace23ca2-f935-53c4-a239-d6cb06d3c042',
  'sdep-ca0575',
  'Noordwijk (inclusief Noordwijkerhout)',
  '2025-01-01 00:00:00+00'::timestamptz
) ON CONFLICT (client_id, competent_authority_id, created_at) DO NOTHING;

-- Gemeente Pijnacker-Nootdorp
INSERT INTO competent_authority (competent_authority_id, client_id, competent_authority_name, created_at)
VALUES (
  '303daae2-4e70-553f-bc7d-c9af7b5c89ac',
  'sdep-ca1926',
  'Pijnacker-Nootdorp',
  '2025-01-01 00:00:00+00'::timestamptz
) ON CONFLICT (client_id, competent_authority_id, created_at) DO NOTHING;

-- Gemeente Renkum
INSERT INTO competent_authority (competent_authority_id, client_id, competent_authority_name, created_at)
VALUES (
  'd7e79bbe-4dff-5ffe-8d9a-d22930d12545',
  'sdep-ca0274',
  'Renkum',
  '2025-01-01 00:00:00+00'::timestamptz
) ON CONFLICT (client_id, competent_authority_id, created_at) DO NOTHING;

-- Gemeente Sluis
INSERT INTO competent_authority (competent_authority_id, client_id, competent_authority_name, created_at)
VALUES (
  '20a03a70-7bab-5cc0-b1f4-396f2f11760c',
  'sdep-ca1714',
  'Sluis',
  '2025-01-01 00:00:00+00'::timestamptz
) ON CONFLICT (client_id, competent_authority_id, created_at) DO NOTHING;

-- Gemeente Schouwen-Duiveland
INSERT INTO competent_authority (competent_authority_id, client_id, competent_authority_name, created_at)
VALUES (
  '08dea277-4956-52df-95d7-8113d1a6e8cc',
  'sdep-ca1676',
  'Schouwen-Duiveland',
  '2025-01-01 00:00:00+00'::timestamptz
) ON CONFLICT (client_id, competent_authority_id, created_at) DO NOTHING;

-- Gemeente Texel
INSERT INTO competent_authority (competent_authority_id, client_id, competent_authority_name, created_at)
VALUES (
  '703b2f59-8aca-5812-b96d-09a6be47e183',
  'sdep-ca0448',
  'Texel',
  '2025-01-01 00:00:00+00'::timestamptz
) ON CONFLICT (client_id, competent_authority_id, created_at) DO NOTHING;

-- Gemeente Utrecht
INSERT INTO competent_authority (competent_authority_id, client_id, competent_authority_name, created_at)
VALUES (
  '7a4039df-9ca4-55f7-9b21-2aa28f4c9da6',
  'sdep-ca0344',
  'Utrecht',
  '2025-01-01 00:00:00+00'::timestamptz
) ON CONFLICT (client_id, competent_authority_id, created_at) DO NOTHING;

-- Gemeente Vlissingen
INSERT INTO competent_authority (competent_authority_id, client_id, competent_authority_name, created_at)
VALUES (
  'acd71d83-5105-5a0e-8dbc-20d5bf761f69',
  'sdep-ca0718',
  'Vlissingen',
  '2025-01-01 00:00:00+00'::timestamptz
) ON CONFLICT (client_id, competent_authority_id, created_at) DO NOTHING;

-- Gemeente Voorschoten
INSERT INTO competent_authority (competent_authority_id, client_id, competent_authority_name, created_at)
VALUES (
  '5fc653b6-ada0-527b-86f1-21a01bebd650',
  'sdep-ca0626',
  'Voorschoten',
  '2025-01-01 00:00:00+00'::timestamptz
) ON CONFLICT (client_id, competent_authority_id, created_at) DO NOTHING;

-- Gemeente Waterland
INSERT INTO competent_authority (competent_authority_id, client_id, competent_authority_name, created_at)
VALUES (
  'e416d9f1-be38-560e-8f50-89af3b935e8f',
  'sdep-ca0852',
  'Waterland',
  '2025-01-01 00:00:00+00'::timestamptz
) ON CONFLICT (client_id, competent_authority_id, created_at) DO NOTHING;

-- Gemeente Zaanstad
INSERT INTO competent_authority (competent_authority_id, client_id, competent_authority_name, created_at)
VALUES (
  '2e665ac8-b3e2-511a-995d-5dfb7a349554',
  'sdep-ca0479',
  'Zaanstad',
  '2025-01-01 00:00:00+00'::timestamptz
) ON CONFLICT (client_id, competent_authority_id, created_at) DO NOTHING;

-- Gemeente Zandvoort
INSERT INTO competent_authority (competent_authority_id, client_id, competent_authority_name, created_at)
VALUES (
  '524dde6b-e353-525e-ac6e-fa56d58222e1',
  'sdep-ca0473',
  'Zandvoort',
  '2025-01-01 00:00:00+00'::timestamptz
) ON CONFLICT (client_id, competent_authority_id, created_at) DO NOTHING;

-- Gemeente Zwolle
INSERT INTO competent_authority (competent_authority_id, client_id, competent_authority_name, created_at)
VALUES (
  '10f2b986-802c-537f-82d2-8069a25c6c11',
  'sdep-ca0193',
  'Zwolle',
  '2025-01-01 00:00:00+00'::timestamptz
) ON CONFLICT (client_id, competent_authority_id, created_at) DO NOTHING;
