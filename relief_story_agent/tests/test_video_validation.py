from relief_story_agent.video_validation import check_local_video_file


def _mp4_box(kind: bytes, payload: bytes = b"") -> bytes:
    return (len(payload) + 8).to_bytes(4, "big") + kind + payload


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
