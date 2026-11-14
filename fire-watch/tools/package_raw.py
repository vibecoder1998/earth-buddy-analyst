"""Package the raw CSVs into fire-watch/raw-data/ exactly as downloaded, with checksums, so the ground truth ships with the code.

    python fire-watch/tools/package_raw.py --firms <folder with fire_archive_*.csv> --giovanni <folder with the 8 Giovanni CSVs>

* the 8 Giovanni files and the FIRMS near-real-time file and readme are copied byte for byte;
* the FIRMS archive (~57 MB) is gzipped (deterministically: no timestamp, so the same input always gives the same .gz) and checked by unpacking it again;
* SHA256SUMS.txt lists the checksum of every original file, and of the .gz.
Nothing in the source folders is modified.
"""
import argparse
import gzip
import hashlib
import shutil
from pathlib import Path

FW = Path(__file__).resolve().parent.parent
RAW = FW / "raw-data"


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--firms", required=True)
    ap.add_argument("--giovanni", required=True)
    a = ap.parse_args()
    (RAW / "giovanni").mkdir(parents=True, exist_ok=True)
    (RAW / "firms").mkdir(parents=True, exist_ok=True)
    sums = []

    g_files = sorted(Path(a.giovanni).glob("*.csv"))
    assert len(g_files) == 8, f"expected 8 Giovanni CSVs, found {len(g_files)}"
    for f in g_files:
        shutil.copy2(f, RAW / "giovanni" / f.name)
        assert sha256(RAW / "giovanni" / f.name) == sha256(f)
        sums.append((sha256(f), f"giovanni/{f.name}"))

    archive = next(Path(a.firms).glob("fire_archive_*.csv"))
    gz = RAW / "firms" / (archive.name + ".gz")
    with open(archive, "rb") as src, open(gz, "wb") as raw_out:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw_out, compresslevel=9, mtime=0) as out:
            shutil.copyfileobj(src, out)
    h = hashlib.sha256()
    with gzip.open(gz, "rb") as back:                      # prove the round trip
        for chunk in iter(lambda: back.read(1 << 20), b""):
            h.update(chunk)
    assert h.hexdigest() == sha256(archive), "the .gz does not unpack to the original file"
    sums.append((sha256(archive), f"firms/{archive.name}  (original, stored as {gz.name})"))
    sums.append((sha256(gz), f"firms/{gz.name}"))

    for name in ("Readme.txt",) + tuple(p.name for p in Path(a.firms).glob("fire_nrt_*.csv")):
        f = Path(a.firms) / name
        if f.exists():
            shutil.copy2(f, RAW / "firms" / name)
            assert sha256(RAW / "firms" / name) == sha256(f)
            sums.append((sha256(f), f"firms/{name}"))

    (RAW / "SHA256SUMS.txt").write_text(
        "SHA-256 of every raw file exactly as downloaded (the FIRMS archive is stored gzipped; its line shows the checksum of the unpacked original, the next line the .gz).\n"
        "Check one file with:  sha256sum <file>   (or: certutil -hashfile <file> SHA256 on Windows)\n\n" + "\n".join(f"{h}  {n}" for h, n in sums) + "\n", encoding="utf-8")
    print(f"packaged {len(g_files)} Giovanni files + FIRMS archive ({archive.stat().st_size / 1e6:.1f} MB -> {gz.stat().st_size / 1e6:.1f} MB gzipped) into {RAW}")


if __name__ == "__main__":
    main()
