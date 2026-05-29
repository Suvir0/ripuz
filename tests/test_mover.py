"""
Tests for app/mover.py — FLAC tag reader + file mover.
Uses mutagen to write real FLAC tags into temporary files.
"""
from pathlib import Path

import pytest
from mutagen.flac import FLAC


def _make_tagged_flac(
    path: Path,
    artist: str = "Test Artist",
    album: str = "Test Album",
    title: str = "Test Title",
    albumartist: str = "",
) -> Path:
    """Create a minimal valid FLAC file at path with the supplied tags."""
    path.parent.mkdir(parents=True, exist_ok=True)
    # Write a bare-minimum FLAC file: 4-byte marker + empty stream
    # mutagen can open and tag a file written as raw bytes as long as we
    # initialise it via FLAC.save() on an empty object first.
    # Easiest approach: copy a known-good tiny FLAC from a fixture if available,
    # otherwise write a minimal STREAMINFO block.
    _write_minimal_flac(path)
    tags = FLAC(path)
    tags["artist"] = [artist]
    tags["album"] = [album]
    tags["title"] = [title]
    if albumartist:
        tags["albumartist"] = [albumartist]
    tags.save()
    return path


def _write_minimal_flac(path: Path) -> None:
    """
    Write a valid minimal FLAC file (no audio frames, just a STREAMINFO block).

    STREAMINFO (34 bytes) must have a non-zero sample_rate or mutagen rejects it.
    Encoding: sample_rate=44100 Hz, channels=1 (mono), bits_per_sample=16,
    total_samples=0, MD5=all-zeros.

    Bit packing (mutagen source):
      sample_first (16 bits) = sample_rate >> 4 = 2756 = 0x0AC4
      sample_tail  (4 bits)  = sample_rate & 0xF = 4
      channels_m1  (3 bits)  = 0  (mono)
      bps_top_bit  (1 bit)   = bps_minus1 >> 4 = 0  (15 < 16)
      bps_bottom4  (4 bits)  = bps_minus1 & 0xF = 0xF
      total_samples (36 bits) = 0
    """
    import struct
    marker = b"fLaC"
    block_header = struct.pack(">I", (1 << 31) | 34)  # last block, type 0, len 34
    streaminfo = (
        b'\x10\x00'             # min_blocksize = 4096
        + b'\x10\x00'           # max_blocksize = 4096
        + b'\x00\x00\x00'       # min_framesize = 0
        + b'\x00\x00\x00'       # max_framesize = 0
        + b'\x0a\xc4'           # sample_first = 2756 (44100 >> 4)
        + b'\x40'               # sample_tail=4 | channels_m1=0 | bps_top=0 → 0x40
        + b'\xf0\x00\x00\x00\x00'  # bps_bottom4=0xF | total_samples=0
        + b'\x00' * 16          # MD5 signature (16 bytes)
    )
    assert len(streaminfo) == 34
    path.write_bytes(marker + block_header + streaminfo)


# ── import under test ─────────────────────────────────────────────────────────

from app.mover import move_album, _sanitize, MoveResult


# ── _sanitize ─────────────────────────────────────────────────────────────────

def test_sanitize_replaces_spaces():
    assert _sanitize("What Did I Miss") == "What_Did_I_Miss"


def test_sanitize_replaces_slash():
    assert "/" not in _sanitize("AC/DC")


def test_sanitize_replaces_backslash():
    assert "\\" not in _sanitize("back\\slash")


def test_sanitize_collapses_runs():
    assert "__" not in _sanitize("a  b")


def test_sanitize_strips_edges():
    result = _sanitize("  hello  ")
    assert not result.startswith("_")
    assert not result.endswith("_")


def test_sanitize_nonempty_fallback():
    assert _sanitize("") == "_"
    assert _sanitize("///") == "_"


def test_sanitize_rejects_dot_components():
    assert _sanitize(".") == "_"
    assert _sanitize("..") == "_"


# ── move_album ────────────────────────────────────────────────────────────────

def test_move_album_basic(tmp_path):
    dl = tmp_path / "downloads" / "Drake" / "ICEMAN"
    music = tmp_path / "music"
    music.mkdir(exist_ok=True)

    _make_tagged_flac(
        dl / "What_Did_I_Miss.flac",
        artist="Drake",
        albumartist="Drake",
        album="ICEMAN",
        title="What Did I Miss",
    )

    result = move_album(dl, music)

    assert len(result.moved) == 1
    assert len(result.skipped) == 0
    dest = music / "Drake" / "ICEMAN" / "What_Did_I_Miss.FLAC"
    assert dest.exists()


def test_move_album_space_to_underscore(tmp_path):
    dl = tmp_path / "downloads" / "artist" / "album"
    music = tmp_path / "music"
    music.mkdir(exist_ok=True)

    _make_tagged_flac(
        dl / "track.flac",
        artist="Some Artist",
        album="Some Album",
        title="Some Title",
    )

    result = move_album(dl, music)

    assert len(result.moved) == 1
    dest = music / "Some_Artist" / "Some_Album" / "Some_Title.FLAC"
    assert dest.exists()


def test_move_album_prefers_albumartist(tmp_path):
    dl = tmp_path / "dl" / "a"
    music = tmp_path / "music"
    music.mkdir(exist_ok=True)

    _make_tagged_flac(
        dl / "t.flac",
        artist="Track Artist",
        albumartist="Album Artist",
        album="Album",
        title="Title",
    )

    result = move_album(dl, music)
    assert len(result.moved) == 1
    dest = music / "Album_Artist" / "Album" / "Title.FLAC"
    assert dest.exists()


def test_move_album_multiple_tracks(tmp_path):
    dl = tmp_path / "dl" / "artist" / "album"
    music = tmp_path / "music"
    music.mkdir(exist_ok=True)

    for i in range(3):
        _make_tagged_flac(
            dl / f"track{i}.flac",
            artist="Artist",
            album="Album",
            title=f"Track {i}",
        )

    result = move_album(dl, music)
    assert len(result.moved) == 3
    assert (music / "Artist" / "Album" / "Track_0.FLAC").exists()
    assert (music / "Artist" / "Album" / "Track_2.FLAC").exists()


def test_move_album_empty_dir(tmp_path):
    dl = tmp_path / "dl" / "empty"
    dl.mkdir(parents=True)
    music = tmp_path / "music"
    music.mkdir(exist_ok=True)

    result = move_album(dl, music)
    assert len(result.moved) == 0
    assert len(result.skipped) == 0


def test_move_album_returns_moveresult_type(tmp_path):
    dl = tmp_path / "dl" / "a"
    music = tmp_path / "music"
    music.mkdir(exist_ok=True)
    _make_tagged_flac(dl / "t.flac", title="T")
    result = move_album(dl, music)
    assert isinstance(result, MoveResult)


def test_move_album_overwrite_existing(tmp_path):
    """If dest already exists, the mover replaces it (no crash)."""
    dl = tmp_path / "dl" / "a"
    music = tmp_path / "music"
    music.mkdir(exist_ok=True)

    _make_tagged_flac(dl / "t.flac", artist="A", album="B", title="T")

    # Pre-populate destination
    dest = music / "A" / "B" / "T.FLAC"
    dest.parent.mkdir(parents=True)
    dest.write_bytes(b"old")

    result = move_album(dl, music)
    assert len(result.moved) == 1
    assert dest.exists()


def test_move_album_fallback_tags(tmp_path):
    """File with no tags gets Unknown_Artist / Unknown_Album / stem.FLAC."""
    dl = tmp_path / "dl" / "a"
    music = tmp_path / "music"
    music.mkdir(exist_ok=True)

    # Write a minimal FLAC with NO tags
    src = dl / "mystery.flac"
    _write_minimal_flac.__func__ if False else None
    src.parent.mkdir(parents=True, exist_ok=True)
    _write_minimal_flac(src)
    tags = FLAC(src)
    tags.clear()
    tags.save()

    result = move_album(dl, music)
    assert len(result.moved) == 1
    dest = music / "Unknown_Artist" / "Unknown_Album" / "mystery.FLAC"
    assert dest.exists()


def test_move_album_carries_lrc_sidecar(tmp_path):
    """A sibling .lrc moves alongside its FLAC with a matching stem."""
    dl = tmp_path / "dl" / "artist" / "album"
    music = tmp_path / "music"
    music.mkdir(exist_ok=True)

    _make_tagged_flac(
        dl / "track.flac",
        artist="Some Artist",
        album="Some Album",
        title="Some Title",
    )
    (dl / "track.lrc").write_text("[00:01.00]hello\n")

    result = move_album(dl, music)

    assert len(result.moved) == 1
    flac_dest = music / "Some_Artist" / "Some_Album" / "Some_Title.FLAC"
    lrc_dest = music / "Some_Artist" / "Some_Album" / "Some_Title.lrc"
    assert flac_dest.exists()
    assert lrc_dest.exists()
    assert lrc_dest.read_text().startswith("[00:01.00]")
    # Source sidecar should be gone (moved, not copied).
    assert not (dl / "track.lrc").exists()


def test_move_album_no_lrc_sidecar_is_fine(tmp_path):
    """Absence of a .lrc sidecar leaves the move unaffected."""
    dl = tmp_path / "dl" / "a"
    music = tmp_path / "music"
    music.mkdir(exist_ok=True)
    _make_tagged_flac(dl / "t.flac", artist="A", album="B", title="T")

    result = move_album(dl, music)

    assert len(result.moved) == 1
    assert not (music / "A" / "B" / "T.lrc").exists()
    assert not result.errors


def test_move_album_skips_path_escape_symlink(tmp_path):
    dl = tmp_path / "dl" / "escape"
    music = tmp_path / "music"
    outside = tmp_path / "outside"
    outside.mkdir(parents=True, exist_ok=True)
    music.mkdir(exist_ok=True)

    # Create a symlink inside the music dir that points outside.
    (music / "SymlinkArtist").symlink_to(outside, target_is_directory=True)

    _make_tagged_flac(
        dl / "t.flac",
        artist="SymlinkArtist",
        album="Album",
        title="Track",
    )

    result = move_album(dl, music)

    assert len(result.moved) == 0
    assert len(result.skipped) == 1
    assert result.errors
    assert not (outside / "Album" / "Track.FLAC").exists()


# ── same-title collision disambiguation ───────────────────────────────────────

def test_move_album_duplicate_title_with_track_numbers(tmp_path):
    """Two tracks sharing a sanitized title are disambiguated via tracknumber tag."""
    from mutagen.flac import FLAC as MutagenFLAC

    dl = tmp_path / "downloads" / "Artist" / "Album"
    music = tmp_path / "music"
    dl.mkdir(parents=True, exist_ok=True)
    music.mkdir(parents=True, exist_ok=True)

    def _make_numbered_flac(filename, tracknumber):
        path = dl / filename
        _write_minimal_flac(path)
        tags = MutagenFLAC(path)
        tags["artist"] = ["Test Artist"]
        tags["album"] = ["Test Album"]
        tags["title"] = ["Intro"]          # same title for both tracks
        tags["tracknumber"] = [str(tracknumber)]
        tags.save()
        return path

    _make_numbered_flac("t01.flac", "1")
    _make_numbered_flac("t02.flac", "2")

    result = move_album(dl, music)

    # Both files must be moved — no data loss
    assert len(result.moved) == 2
    assert not result.skipped

    # The destinations must be distinct
    moved_names = {p.name for p in result.moved}
    assert len(moved_names) == 2, f"Expected 2 distinct names, got: {moved_names}"


def test_move_album_duplicate_title_fallback_counter(tmp_path):
    """Without track number tags the counter suffix prevents data loss."""
    from mutagen.flac import FLAC as MutagenFLAC

    dl = tmp_path / "downloads" / "Artist" / "Album"
    music = tmp_path / "music"
    dl.mkdir(parents=True, exist_ok=True)
    music.mkdir(parents=True, exist_ok=True)

    for idx, filename in enumerate(["a.flac", "b.flac", "c.flac"]):
        path = dl / filename
        _write_minimal_flac(path)
        tags = MutagenFLAC(path)
        tags["artist"] = ["Test Artist"]
        tags["album"] = ["Test Album"]
        tags["title"] = ["Hidden Track"]   # all three share the same title; no tracknumber
        tags.save()

    result = move_album(dl, music)

    assert len(result.moved) == 3
    assert not result.skipped
    # All destinations must be distinct
    assert len({p.name for p in result.moved}) == 3


def test_move_album_no_collision_unchanged_layout(tmp_path):
    """When titles are unique the output path must be exactly Title.FLAC (no suffix)."""
    dl = tmp_path / "downloads" / "Artist" / "Album"
    music = tmp_path / "music"
    dl.mkdir(parents=True, exist_ok=True)
    music.mkdir(parents=True, exist_ok=True)

    _make_tagged_flac(dl / "a.flac", title="Opening")
    _make_tagged_flac(dl / "b.flac", title="Closing")

    result = move_album(dl, music)

    assert len(result.moved) == 2
    names = {p.name for p in result.moved}
    assert "Opening.FLAC" in names
    assert "Closing.FLAC" in names
