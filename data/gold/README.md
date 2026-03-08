# Gold Labels

This directory stores manually maintained benchmark labels for curated official-seed runs.

## Purpose

- Benchmark extraction quality against known expected field values.
- Keep the benchmark deterministic and editable by hand.
- Separate manually curated truth data from runtime outputs.

## File Naming

- Official-seed gold labels live under `data/gold/official-seed/`.
- Each benchmark file should be named `<PROGRAM_CODE>.json`.

## Recommended Workflow

1. Copy `data/gold/official-seed/template.json` to `data/gold/official-seed/<PROGRAM_CODE>.json`.
2. Fill in `program_code`, `university`, and `coverage_expectations` from the curated target definition.
3. Manually read the official seed pages or the checked-in raw official-seed captures for that program.
4. Fill only the fields you have verified by hand.
5. Leave unknown fields as `null` or `[]` until they are manually confirmed.
6. Change `label_status` from a template value to a curated value only after manual review.

## Label Status Conventions

- `manual_template_pending`: the file is a scaffold for manual curation and should still be reviewed field by field.
- `manually_curated_example`: the file is a checked example benchmark label.
- `manually_curated`: the file is intended to be treated as a finished benchmark label.

## Minimal Schema

```json
{
  "program_code": "HKU_MSC_AI",
  "university": "HKU",
  "mode": "official_seed",
  "label_status": "manually_curated",
  "notes": "Optional human notes about how this label was curated.",
  "coverage_expectations": {
    "program_name": true,
    "deadline": true,
    "tuition": true,
    "english_requirement": false,
    "academic_requirement": true,
    "prerequisite_keywords": true
  },
  "fields": {
    "program_name": "Master of Science in Artificial Intelligence",
    "deadline": "December 1, 2025",
    "tuition": "The tuition fee is HK$390,000...",
    "english_requirement": null,
    "academic_requirement": "Applicants shall hold a Bachelor's degree...",
    "prerequisite_keywords": [
      "statistics",
      "probability"
    ]
  }
}
```

## Notes

- `coverage_expectations` is optional. If omitted, benchmarking falls back to the official seed-page `intended_fields`.
- `label_status` should make it obvious whether the file is a finished benchmark label or only an example/template.
- Do not auto-generate these files from the web. Edit them manually.
- For `HKU_MDASC`, start from `data/gold/official-seed/HKU_MDASC.json`, review the curated official seed pages, then run the benchmark command after filling the fields.
- For `HKUST_MSC_BDT`, start from `data/gold/official-seed/HKUST_MSC_BDT.json`, curate fields manually, then run the official-seed benchmark command.
