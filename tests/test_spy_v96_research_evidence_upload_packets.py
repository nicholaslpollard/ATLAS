from __future__ import annotations

"""V96 evidence packet construction has no provider or broker dependencies."""

import hashlib
import json
from pathlib import Path
import zipfile

import pytest

from scripts.run_spy_v96_research_evidence_upload_packets import (
    BundleError,collect,run,split_chunks,
)


def make_zip(folder:Path,name:str,data:str="original") -> Path:
    f=folder/name
    with zipfile.ZipFile(f,"x") as z:
        z.writestr("summary.json",data)
    return f


def test_pack_only_original_relevant_zip_and_verify_embedded_sha(tmp_path):
    research=tmp_path/"research";research.mkdir()
    destination=tmp_path/"out";destination.mkdir()
    old=make_zip(research,"spy_v95_eight_complete_regimes_2020_censored_matrix_20261101.zip")
    another=make_zip(research,"spy_v93_v90_six_families_2019_full_test.zip")
    make_zip(research,"totally_unrelated_provider_or_private.zip")
    original_hashes={
        f.name:hashlib.sha256(f.read_bytes()).hexdigest()
        for f in (old,another)
    }
    result=run(research,destination,max_part_mib=10,stamp="test",
               reporter=lambda _:None)
    assert result["original_evidence_file_count"]==2
    assert result["packet_count"]==1
    assert result["no_provider_calls"] and result["no_broker_orders"]
    assert result["missing_expected_stage_prefixes"]
    packet=destination/"atlas_v96_upload_packets_test"/result["packets"][0]["packet"]
    assert packet.is_file()
    with zipfile.ZipFile(packet) as z:
        assert z.testzip() is None
        manifest=json.loads(z.read("MANIFEST.json"))
        assert manifest["original_files_modified"] is False
        assert not manifest["option_cache_or_database_included"]
        for row in manifest["original_files"]:
            assert row["source_sha256"]==original_hashes[row["name"]]
            assert (hashlib.sha256(z.read("research/"+row["name"]))
                    .hexdigest()==row["source_sha256"])
        assert "research/totally_unrelated_provider_or_private.zip" not in z.namelist()
    for f in (old,another):
        assert hashlib.sha256(f.read_bytes()).hexdigest()==original_hashes[f.name]


def test_fallback_directory_only_when_original_stage_zip_absent(tmp_path):
    research=tmp_path/"research";research.mkdir()
    output=tmp_path/"out";output.mkdir()
    folder=research/"spy_v95_v89_six_families_2021_full_missingzip"
    folder.mkdir()
    (folder/"summary.json").write_text("{}")
    (folder/"source_events.jsonl").write_text('{"sequence":1}\n')
    (folder/"excluded.sqlite").write_bytes(b"never package DB")
    result=run(research,output,max_part_mib=10,stamp="missing",
               reporter=lambda _:None)
    with zipfile.ZipFile(output/"atlas_v96_upload_packets_missing"/
                         result["packets"][0]["packet"]) as z:
        names=z.namelist()
        assert any(p.endswith("/summary.json") for p in names)
        assert any(p.endswith("/source_events.jsonl") for p in names)
        assert not any(p.endswith(".sqlite") for p in names)
    assert any("UNSUPPORTED_EXTENSION" in s for s in result["missing_expected_stage_prefixes"])


def test_chunk_boundary_and_safety_guards(tmp_path):
    research=tmp_path/"research";research.mkdir()
    output=tmp_path/"out";output.mkdir()
    sample=make_zip(research,"spy_v95_original_2020_read_only_reconciliation_test.zip")
    assert len(split_chunks([(sample,"one"),(sample,"two")],sample.stat().st_size))==2
    with pytest.raises(BundleError,match="PACKET_LIMIT"):
        run(research,output,max_part_mib=1,reporter=lambda _:None)
    empty=tmp_path/"empty";empty.mkdir()
    with pytest.raises(BundleError,match="NO_RELEVANT"):
        collect(empty)


def test_corrupt_original_zip_rejected_before_packet_claim(tmp_path):
    research=tmp_path/"research";research.mkdir()
    output=tmp_path/"out";output.mkdir()
    (research/"spy_v95_eight_complete_regimes_2020_censored_matrix_invalid.zip").write_bytes(
        b"not a ZIP archive"
    )
    with pytest.raises(BundleError,match="ORIGINAL_RESEARCH_ZIP_INVALID"):
        run(research,output,max_part_mib=10,stamp="corrupt",reporter=lambda _:None)


def test_output_never_included_as_input(tmp_path):
    research=tmp_path/"research";research.mkdir()
    make_zip(research,"spy_v95_eight_complete_regimes_2020_censored_matrix_test.zip")
    run(research,research,max_part_mib=10,stamp="one",reporter=lambda _:None)
    result=run(research,research,max_part_mib=10,stamp="two",reporter=lambda _:None)
    assert result["original_evidence_file_count"]==1
