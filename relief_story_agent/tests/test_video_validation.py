from relief_story_agent.video_validation import check_local_video_file


def _mp4_box(kind: bytes, payload: bytes = b"") -> bytes:
    return (len(payload) + 8).to_bytes(4, "big") + kind + payload


def _webm_header() -> bytes:
    return b"\x1a\x45\xdf\xa3\x42\x82\x84webm"


def test_non_mp4_video_extensions_with_bad_headers_are_not_openable(tmp_path):
    cases = {
        "webm": b"not a webm",
        "mkv": b"not a matroska file",
        "avi": b"not an avi",
    }
    for suffix, payload in cases.items():
        path = tmp_path / f"bad.{suffix}"
        path.write_bytes(payload)

        result = check_local_video_file(str(path))

        assert result["exists"] is True
        assert result["size_bytes"] > 0
        assert result["openable"] is False
        assert result["valid"] is False


def test_webm_with_ebml_doctype_is_openable(tmp_path):
    path = tmp_path / "container.webm"
    path.write_bytes(_webm_header() + b"\x00")

    result = check_local_video_file(str(path))

    assert result["openable"] is True
    assert result["valid"] is True


def test_mkv_with_matroska_doctype_is_openable(tmp_path):
    path = tmp_path / "container.mkv"
    path.write_bytes(b"\x1a\x45\xdf\xa3\x42\x82\x88matroska\x00")

    result = check_local_video_file(str(path))

    assert result["openable"] is True
    assert result["valid"] is True


def test_avi_with_riff_avi_header_is_openable(tmp_path):
    path = tmp_path / "container.avi"
    path.write_bytes(b"RIFF\x04\x00\x00\x00AVI \x00")

    result = check_local_video_file(str(path))

    assert result["openable"] is True
    assert result["valid"] is True


def test_mp4_with_only_ftyp_box_is_not_openable(tmp_path):
    path = tmp_path / "ftyp_only.mp4"
    path.write_bytes(_mp4_box(b"ftyp", b"isom\x00\x00\x02\x00isomiso2"))

    result = check_local_video_file(str(path))

    assert result["exists"] is True
    assert result["size_bytes"] > 0
    assert result["openable"] is False
    assert result["valid"] is False


def test_mp4_with_ftyp_and_moov_boxes_is_openable(tmp_path):
    path = tmp_path / "container.mp4"
    path.write_bytes(
        _mp4_box(b"ftyp", b"isom\x00\x00\x02\x00isomiso2")
        + _mp4_box(b"moov", b"\x00")
    )

    result = check_local_video_file(str(path))

    assert result["openable"] is True
    assert result["valid"] is True
