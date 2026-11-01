from __future__ import annotations

"""V96 — bundle relevant immutable ATLAS research evidence into upload packets.

Reads historical V83–V95 local research ZIPs, plus matching signed report files
only when a ZIP is missing. Does NOT read the provider cache, secrets, DB,
historical stock source parquet, or news provider raw corpus. Zero network,
provider, broker and trade actions. Original evidence is NEVER modified.
"""

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ALLOWED = re.compile(r"^spy_v(?:8[3-9]|9[0-5])_",re.ASCII)
SAFE_LOOSE_SUFFIX = frozenset((".json",".jsonl",".gz",".csv",".txt",".md"))
DEFAULT_MAX_PART_MIB = 90

REQUIRED_PREFIXES = (
    "spy_v89_six_new_families_2024_full_",
    "spy_v90_six_new_families_2024_full_",
    "spy_v89_six_new_families_2025_h2_",
    "spy_v90_six_new_families_2025_h2_",
    "spy_v89_six_new_families_2026_janapr_",
    "spy_v90_six_new_families_2026_janapr_",
    "spy_v91_six_new_family_three_cohort_matrix_",
    "spy_v92_pre2024_original_stock_inventory_",
    "spy_v93_preflight_2018_2023_",
    "spy_v93_v89_six_families_2018_full_",
    "spy_v93_v90_six_families_2018_full_",
    "spy_v93_v89_six_families_2019_full_",
    "spy_v93_v90_six_families_2019_full_",
    "spy_v93_v89_six_families_2020_full_",
    "spy_v95_original_2020_read_only_reconciliation_",
    "spy_v95_v89_six_families_2021_full_",
    "spy_v95_v90_six_families_2021_full_",
    "spy_v95_v89_six_families_2022_full_",
    "spy_v95_v90_six_families_2022_full_",
    "spy_v95_v89_six_families_2023_full_",
    "spy_v95_v90_six_families_2023_full_",
    "spy_v95_eight_complete_regimes_2020_censored_matrix_",
)


class BundleError(ValueError):
    pass


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fp:
        for buf in iter(lambda: fp.read(1024 * 1024), b""):
            h.update(buf)
    return h.hexdigest()


def collect(research_dir: Path) -> tuple[list[tuple[Path,str]],list[str]]:
    if not research_dir.is_dir() or research_dir.is_symlink():
        raise BundleError("RESEARCH_EVIDENCE_ROOT_INVALID")
    entries=[]
    skipped=[]
    # Do NOT descend the whole research tree, raw options cache, or provider
    # data lake. A local original ZIP takes precedence over duplicate loose files.
    children=sorted(research_dir.iterdir(),key=lambda x:x.name)
    for item in children:
        if not ALLOWED.match(item.name):
            continue
        if item.is_symlink():
            skipped.append(f"SYMLINK_IGNORED:{item.name}")
            continue
        if item.is_file() and item.suffix==".zip":
            entries.append((item,item.name))
    zipped_stems={x.name[:-4] for x,_ in entries}
    for item in children:
        if (not ALLOWED.match(item.name) or not item.is_dir()
                or item.is_symlink() or item.name in zipped_stems):
            continue
        for f in sorted(item.rglob("*"),key=lambda p:p.as_posix()):
            if f.is_symlink():
                skipped.append(f"SYMLINK_IGNORED:{f.relative_to(research_dir).as_posix()}")
                continue
            if not f.is_file():
                continue
            if f.suffix.lower() not in SAFE_LOOSE_SUFFIX:
                skipped.append(f"UNSUPPORTED_EXTENSION:{f.relative_to(research_dir).as_posix()}")
                continue
            entries.append((f,f.relative_to(research_dir).as_posix()))
    if not entries:
        raise BundleError("NO_RELEVANT_V83_V95_SIGNED_RESEARCH_EVIDENCE_FOUND")
    names={alias for _,alias in entries}
    miss=[p for p in REQUIRED_PREFIXES if not any(n.startswith(p) for n in names)]
    return sorted(entries,key=lambda x:x[1]),miss+skipped


def split_chunks(files: list[tuple[Path,str]],max_bytes: int):
    chunks=[]
    current=[]
    current_bytes=0
    for original,alias in files:
        size=original.stat().st_size
        if current and current_bytes+size>max_bytes:
            chunks.append(current)
            current=[]
            current_bytes=0
        current.append((original,alias))
        current_bytes+=size
    if current:
        chunks.append(current)
    return chunks


def run(research_dir: Path,output_parent: Path,*,max_part_mib=90,
        stamp: str | None = None, reporter=print) -> dict:
    if (type(max_part_mib) is not int or not 10<=max_part_mib<=512
            or not output_parent.is_dir() or output_parent.is_symlink()):
        raise BundleError("PACKET_LIMIT_OR_OUTPUT_PARENT_INVALID")
    files,missing=collect(research_dir)
    packet_groups=split_chunks(files,max_part_mib*1024*1024)
    stamp=stamp or datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    output=output_parent/f"atlas_v96_upload_packets_{stamp}"
    if output.exists() or output.is_symlink():
        raise BundleError("UPLOAD_DIRECTORY_ALREADY_EXISTS")
    output.mkdir(parents=True,exist_ok=False)
    payloads=[]
    for index,group in enumerate(packet_groups,1):
        destination=output/f"atlas_v96_evidence_part_{index:03d}.zip"
        members=[]
        for original,alias in group:
            if original.is_symlink() or not original.is_file():
                raise BundleError("SOURCE_FILE_CHANGED_OR_BECAME_SYMLINK")
            if original.suffix==".zip":
                try:
                    with zipfile.ZipFile(original,"r") as source_zip:
                        if source_zip.testzip() is not None:
                            raise BundleError("EXISTING_ORIGINAL_RESEARCH_ZIP_CRC_INVALID")
                except zipfile.BadZipFile as exc:
                    raise BundleError("EXISTING_ORIGINAL_RESEARCH_ZIP_INVALID") from exc
            members.append({
                "name":alias,
                "source_size_bytes":original.stat().st_size,
                "source_sha256":_sha(original),
            })
        manifest={
            "contract":"atlas-v96-read-only-evidence-upload-packet-v1",
            "part_number":index,
            "source_root_description":"data/research verified stage reports only",
            "input_count":len(members),
            "original_files":members,
            "missing_expected_stage_prefixes":missing,
            "original_files_modified":False,
            "option_cache_or_database_included":False,
            "news_raw_data_included":False,
            "provider_calls":0,"broker_orders":0,
        }
        with zipfile.ZipFile(destination,"x",allowZip64=True) as z:
            for original,alias in group:
                # Existing ZIPs are already compressed. Do not waste CPU or
                # introduce a second lossy transformation.
                compression=(zipfile.ZIP_STORED if original.suffix==".zip"
                             else zipfile.ZIP_DEFLATED)
                z.write(original,arcname=f"research/{alias}",compress_type=compression)
            z.writestr("MANIFEST.json",json.dumps(manifest,sort_keys=True,
                indent=2,ensure_ascii=True)+"\n",compress_type=zipfile.ZIP_DEFLATED)
        # Full CRC verification of the newly created packet, not merely a
        # successful zipfile close. Original file SHA recorded in manifest.
        with zipfile.ZipFile(destination) as check:
            if check.testzip() is not None or len(check.namelist())!=len(members)+1:
                raise BundleError("NEW_EVIDENCE_UPLOAD_PACKET_CRC_INVALID")
            for m in members:
                digest=hashlib.sha256()
                with check.open(f"research/{m['name']}") as inp:
                    for part in iter(lambda:inp.read(1024*1024),b""):
                        digest.update(part)
                if digest.hexdigest()!=m["source_sha256"]:
                    raise BundleError("SOURCE_CHANGED_DURING_EVIDENCE_PACKAGING")
        payloads.append({
            "packet":destination.name,
            "packet_bytes":destination.stat().st_size,
            "packet_sha256":_sha(destination),
            "original_files":len(group),
        })
        reporter(f"V96_PACKET {index}/{len(packet_groups)} "
                 f"file={destination.name} originals={len(group)} "
                 f"bytes={destination.stat().st_size} crc=PASS "
                 "provider_calls=0 broker_orders=0")
    summary={
        "contract":"atlas-v96-read-only-evidence-upload-index-v1",
        "packet_count":len(payloads),"original_evidence_file_count":len(files),
        "packets":payloads,"missing_expected_stage_prefixes":missing,
        "source_files_unmodified":True,
        "no_provider_calls":True,"no_broker_orders":True,
        "output_folder":str(output),
        "instruction":"Upload ALL atlas_v96_evidence_part_*.zip files. Each ZIP has its own MANIFEST.json.",
    }
    indexpath=output/"UPLOAD_INDEX.json"
    with indexpath.open("x",encoding="utf8") as fp:
        json.dump(summary,fp,indent=2,sort_keys=True,ensure_ascii=True)
        fp.write("\n")
        fp.flush()
        os.fsync(fp.fileno())
    reporter(f"COMPLETE V96 packets={len(payloads)} originals={len(files)} "
             f"expected_missing={len(missing)} directory={output} "
             "provider_calls=0 broker_orders=0")
    return summary


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--research-dir",type=Path,default=ROOT/"data"/"research")
    p.add_argument("--output-parent",type=Path,default=ROOT/"data"/"research")
    p.add_argument("--max-part-mib",type=int,default=DEFAULT_MAX_PART_MIB)
    args=p.parse_args(argv)
    try:
        run(args.research_dir,args.output_parent,max_part_mib=args.max_part_mib)
        return 0
    except (OSError,BundleError,ValueError,zipfile.BadZipFile) as exc:
        print(f"STOP V96 evidence packaging error_type={type(exc).__name__} "
              "provider_calls=0 broker_orders=0",flush=True)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
