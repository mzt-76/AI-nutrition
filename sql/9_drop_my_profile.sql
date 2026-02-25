-- Migration 9: Drop legacy my_profile table
-- Applied: 2026-02-25
-- NOTE: Run AFTER all code references to my_profile have been removed

DROP TABLE IF EXISTS my_profile CASCADE;
