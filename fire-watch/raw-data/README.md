# Raw data, exactly as downloaded

These are the raw NASA files every number in the tabs comes from. **Do not edit them**: the scripts only read them, and `SHA256SUMS.txt` lets anyone confirm a file is unchanged.

| Folder | Files | What it is |
|---|---|---|
| `giovanni/` | 8 CSV files | NASA Giovanni monthly area-average time series, January 2001 to December 2024, one box over Cambodia (102.3–107.6°E, 10.4–14.7°N): GPM IMERG rain, and MERRA-2 land rain, root-zone soil wetness, 2 m air temperature, 2 m wet-bulb temperature, aerosol optical depth, black carbon and PM2.5. Each file's first lines record the Giovanni request that produced it, including a link to reproduce it (needs a free NASA Earthdata login). |
| `firms/` | `fire_archive_M-C61_846286.csv.gz`, `fire_nrt_M-C61_846286.csv`, `Readme.txt` | NASA FIRMS active-fire detections, MODIS Collection 6.1 (Terra and Aqua), Cambodia, 16 Nov 2001 to 27 Aug 2026 (717,185 rows). The archive is stored gzipped (57 MB unpacked, 12 MB packed). The near-real-time file (115 rows) is kept for the record and never used. `Readme.txt` is the pointer FIRMS put in the download. |

## Use them

```bash
# unpack the FIRMS archive next to the readme (keeps the .gz)
gunzip -k fire-watch/raw-data/firms/fire_archive_M-C61_846286.csv.gz

# check a file against the recorded fingerprint (Windows: certutil -hashfile <file> SHA256)
sha256sum fire-watch/raw-data/firms/fire_archive_M-C61_846286.csv   # compare with SHA256SUMS.txt

# audit them, and rebuild the clean data and the pages (see ../README.md)
python fire-watch/tools/audit_raw.py --firms fire-watch/raw-data/firms --giovanni fire-watch/raw-data/giovanni
```

## Notes

- The repo's `data/giovanni/` holds the same eight files, used by the Earth Buddy app; they have the same content (the `data/giovanni/` copies show Windows line endings because git rewrote them). These copies are kept byte for byte: `.gitattributes` switches line-ending conversion off for this folder.
- The 57 MB archive is kept gzipped so the repo stays small. The .gz is made deterministically (no timestamp) by `tools/package_raw.py`, and the unpacked file's checksum is the one in `SHA256SUMS.txt`.
- Cite NASA FIRMS and NASA GES DISC (Giovanni) when you use these files. The DOI of each product is in `../README.md`.
