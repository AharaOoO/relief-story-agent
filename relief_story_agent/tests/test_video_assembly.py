from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from relief_story_agent.video_assembly import assemble_segment_videos


def test_assembler_preserves_supplied_story_order(tmp_path):
    clip2 = tmp_path / "segment-002.mp4"
    clip1 = tmp_path / "segment-001.mp4"
    clip2.write_bytes(b"two")
    clip1.write_bytes(b"one")
    output = tmp_path / "final.mp4"

    def runner(command, **kwargs):
        Path(command[-1]).write_bytes(b"assembled")
        return SimpleNamespace(returncode=0, stderr="")

    result = assemble_segment_videos(
        [clip2, clip1],
        output,
        ffmpeg_executable="ffmpeg-test",
        runner=runner,
    )

    manifest = Path(result.concat_manifest_path).read_text(encoding="utf-8")
    assert manifest.index(str(clip2).replace("\\", "/")) < manifest.index(
        str(clip1).replace("\\", "/")
    )
    assert result.status == "completed"
    assert output.read_bytes() == b"assembled"


def test_failed_assembly_preserves_all_clips(tmp_path):
    clips = [tmp_path / "one.mp4", tmp_path / "two.mp4"]
    for index, clip in enumerate(clips):
        clip.write_bytes(f"clip-{index}".encode())
    original = [clip.read_bytes() for clip in clips]

    def runner(command, **kwargs):
        return SimpleNamespace(returncode=1, stderr="encoder failed")

    result = assemble_segment_videos(
        clips,
        tmp_path / "final.mp4",
        ffmpeg_executable="ffmpeg-test",
        runner=runner,
    )

    assert result.status == "failed"
    assert result.return_code == 1
    assert "encoder failed" in result.stderr_tail
    assert [clip.read_bytes() for clip in clips] == original
    assert not (tmp_path / "final.mp4").exists()
