"""The deterministic parsers, in isolation: the CSV record counter and
header reader every validator runs over the committed bytes, the evidence
location grammar, the requirement parameters, and the pure policy
functions."""

import pytest

from tests.direct.support import DATASET, sha256_hex


# -- _dataset_facts ---------------------------------------------------------------

def facts(module, text):
    body = text if isinstance(text, bytes) else text.encode("utf-8")
    return module._dataset_facts(body)


def test_canonical_dataset(module):
    rows, columns = facts(module, DATASET)
    assert rows == 10240
    assert columns == ["observation_id", "compound_id", "target", "assay", "ic50_nm",
                       "replicate", "validated"]


@pytest.mark.parametrize("text,rows,columns", [
    ("a,b\n1,2\n3,4\n", 2, ["a", "b"]),
    ("a,b\n1,2\n3,4", 2, ["a", "b"]),                       # no trailing newline
    ("a,b\r\n1,2\r\n3,4\r\n", 2, ["a", "b"]),               # CRLF
    ("﻿a,b\n1,2\n", 1, ["a", "b"]),                     # byte-order mark
    ("a,b\n1,2\n\n\n3,4\n\n", 2, ["a", "b"]),               # blank records are not counted
    ("a,b\n   \n1,2\n", 1, ["a", "b"]),                      # whitespace-only record
    (" a , b \n1,2\n", 1, ["a", "b"]),                       # header fields are trimmed
    ('"a","b"\n1,2\n', 1, ["a", "b"]),                       # quoted header fields
    ('"a,x","b"\n"1,2",3\n', 1, ["a,x", "b"]),               # commas inside quotes
    ('a,b\n"line\none",2\n3,4\n', 2, ["a", "b"]),            # newline inside quotes is one record
    ('a,b\n"say ""hi""",2\n', 1, ["a", "b"]),                # escaped quotes
    ('"say ""hi""",b\n1,2\n', 1, ['say "hi"', "b"]),
    ("a,b\n", 0, ["a", "b"]),                                # header only
    ("a,b", 0, ["a", "b"]),
    ("", 0, []),
    ("\n\n", 0, []),
    ("a,,b\n1,2,3\n", 1, ["a", "b"]),                        # empty header names dropped
    ("a;b\n1;2\n", 1, ["a;b"]),                              # semicolons are not separators
])
def test_record_and_header_rules(module, text, rows, columns):
    assert facts(module, text) == (rows, columns)


def test_undecodable_bytes_are_replaced_not_rejected(module):
    rows, columns = facts(module, b"a,b\n\xff\xfe,2\n3,4\n")
    assert rows == 2 and columns == ["a", "b"]


def test_column_count_is_capped(module):
    header = ",".join("c%d" % i for i in range(80))
    rows, columns = facts(module, header + "\n1\n")
    assert rows == 1 and len(columns) == 64


def test_unbalanced_quote_swallows_the_rest_as_one_record(module):
    # A stray quote opens a field that never closes: everything after it is
    # one record, on every node alike.
    rows, columns = facts(module, 'a,b\n"open,2\n3,4\n5,6\n')
    assert rows == 1 and columns == ["a", "b"]


def test_split_csv_record(module):
    assert module._split_csv_record("a,b,c") == ["a", "b", "c"]
    assert module._split_csv_record(' a ,"b, c" ,c') == ["a", "b, c", "c"]
    assert module._split_csv_record('"x""y",z') == ['x"y', "z"]
    assert module._split_csv_record("") == [""]
    assert module._split_csv_record("a,") == ["a", ""]


# -- _classify_url ------------------------------------------------------------------

SHA = "a" * 40


@pytest.mark.parametrize("url,host", [
    ("https://raw.githubusercontent.com/o/r/" + SHA + "/f.csv", "raw.githubusercontent.com"),
    ("https://raw.githubusercontent.com/Hemmy1417/DiscoMile/" + SHA + "/fixtures/project/dataset/observations.csv",
     "raw.githubusercontent.com"),
    ("https://zenodo.org/records/14330132/files/dataset_dummy_nodes.csv?download=1", "zenodo.org"),
    ("https://zenodo.org/records/1/files/a.b-c_d?download=1", "zenodo.org"),
])
def test_accepted_locations(module, url, host):
    assert module._classify_url(url) == host


@pytest.mark.parametrize("url", [
    "https://raw.githubusercontent.com/o/r/" + SHA[:-1] + "/f.csv",
    "https://raw.githubusercontent.com/o/r/" + SHA + "/dir/",
    "https://raw.githubusercontent.com/o/r/" + SHA + "/./f.csv",
    "https://raw.githubusercontent.com/o/r/" + SHA,
    "https://raw.githubusercontent.com/o/" + SHA + "/f.csv",
    "https://raw.githubusercontent.com/o/r/" + SHA + "/f.csv?raw=1",
    "https://raw.githubusercontent.com/o/r/" + SHA + "/f.csv#x",
    "https://zenodo.org/records/14330132/files/dataset.csv",
    "https://zenodo.org/records/14330132/files/dataset.csv?download=0",
    "https://zenodo.org/records/14330132/files/?download=1",
    "https://zenodo.org/records/1234567890123/files/a.csv?download=1",
    "https://zenodo.org/api/records/14330132/files/a.csv/content",
    "https://sandbox.zenodo.org/records/1/files/a.csv?download=1",
    "ftp://raw.githubusercontent.com/o/r/" + SHA + "/f.csv",
    "https://raw.githubusercontent.com/o/r/" + SHA + "/fé.csv",
    "https://raw.githubusercontent.com/o/r/" + SHA + "/f.csv\n",
    None,
    42,
])
def test_refused_locations(module, url):
    assert module._classify_url(url) is None


# -- requirement parameters -----------------------------------------------------------

def test_row_count_param(module):
    assert module._parse_row_count_param("1") == 1
    assert module._parse_row_count_param("10000") == 10000
    assert module._parse_row_count_param("1000000000") == 1000000000
    for bad in ("0", "1000000001", "", "12a", "-1", " 1", "1.0", None, 5):
        assert module._parse_row_count_param(bad) is None


def test_columns_param(module):
    assert module._parse_columns_param("a") == ["a"]
    assert module._parse_columns_param(" a , b ") == ["a", "b"]
    assert module._parse_columns_param("compound_id,target,assay,ic50_nm,validated") == [
        "compound_id", "target", "assay", "ic50_nm", "validated"]
    for bad in ("", " ", ",", "a,,b", "a,a", 'a,"b"', "a b", "x" * 65,
                ",".join("c%d" % i for i in range(65)), None):
        assert module._parse_columns_param(bad) is None


# -- pure policy functions ----------------------------------------------------------------

def test_accessible_finding(module):
    assert module._accessible_finding("EXAMINED") == "SATISFIED"
    assert module._accessible_finding("NOT_FOUND") == "NOT_SATISFIED"
    assert module._accessible_finding("EMPTY") == "NOT_SATISFIED"
    for status in ("UNAVAILABLE", "HASH_MISMATCH", "TOO_LARGE"):
        assert module._accessible_finding(status) == "UNVERIFIABLE"


def rows_with(status="EXAMINED", row_count=10240, column_count=7):
    return [{"source_id": "dataset", "kind": "DATASET", "status": status,
             "hash_match": "MATCH" if status == "EXAMINED" else "UNCHECKED",
             "byte_count": 1 if status == "EXAMINED" else 0,
             "row_count": row_count, "column_count": column_count}]


def test_deterministic_findings(module):
    cols = {"dataset": ["observation_id", "compound_id", "target"]}
    m1 = {"requirement_id": "M1", "kind": "ROW_COUNT_MIN", "criterion": "c",
          "source_id": "dataset", "param": "10000"}
    m2 = {"requirement_id": "M2", "kind": "COLUMNS_REQUIRED", "criterion": "c",
          "source_id": "dataset", "param": "compound_id,target"}
    m5 = {"requirement_id": "M5", "kind": "ACCESSIBLE", "criterion": "c",
          "source_id": "dataset", "param": ""}
    m6 = {"requirement_id": "M6", "kind": "DEADLINE", "criterion": "c",
          "source_id": "", "param": ""}
    m3 = {"requirement_id": "M3", "kind": "SEMANTIC", "criterion": "c",
          "source_id": "", "param": ""}
    f = module._deterministic_finding
    assert f(m1, rows_with(), cols, True) == "SATISFIED"
    assert f(m1, rows_with(row_count=9999), cols, True) == "NOT_SATISFIED"
    assert f(m1, rows_with(status="NOT_FOUND", row_count=0), cols, True) == "UNVERIFIABLE"
    assert f(m2, rows_with(), cols, True) == "SATISFIED"
    assert f(m2, rows_with(), {"dataset": ["compound_id"]}, True) == "NOT_SATISFIED"
    assert f(m2, rows_with(), {}, True) == "UNVERIFIABLE"
    assert f(m2, rows_with(status="EMPTY", row_count=0, column_count=0), cols, True) == "UNVERIFIABLE"
    assert f(m5, rows_with(), cols, True) == "SATISFIED"
    assert f(m5, rows_with(status="NOT_FOUND"), cols, True) == "NOT_SATISFIED"
    assert f(m5, rows_with(status="TOO_LARGE"), cols, True) == "UNVERIFIABLE"
    assert f(m6, [], {}, True) == "SATISFIED"
    assert f(m6, [], {}, False) == "NOT_SATISFIED"
    assert f(m3, rows_with(), cols, True) is None
    ghost = dict(m1, source_id="ghost")
    assert f(ghost, rows_with(), cols, True) == "UNVERIFIABLE"


def test_verdict_derivation(module):
    d = module._derive_verdict
    assert d(True, ["SATISFIED", "SATISFIED"]) == "QUALIFIED"
    assert d(True, []) == "QUALIFIED"
    assert d(False, ["SATISFIED"]) == "NOT_QUALIFIED"
    assert d(True, ["SATISFIED", "NOT_SATISFIED", "UNVERIFIABLE"]) == "NOT_QUALIFIED"
    assert d(True, ["SATISFIED", "UNVERIFIABLE"]) == "INCONCLUSIVE"


def test_normalizers(module):
    assert module._normalize_deadline("2026-12-01") == "2026-12-01T23:59:59Z"
    assert module._normalize_deadline("2026-02-29") is None
    assert module._normalize_deadline("2028-02-29") == "2028-02-29T23:59:59Z"
    assert module._normalize_instant("2026-09-06T12:00:00.123456+00:00") == "2026-09-06T12:00:00Z"
    assert module._normalize_instant("2026-09-06 12:00:00") == "2026-09-06T12:00:00Z"
    assert module._normalize_instant("yesterday") is None
    assert module._sha256_hex("abc") == sha256_hex("abc")
