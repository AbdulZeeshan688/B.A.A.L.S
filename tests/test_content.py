import json
import shutil

import pytest

from rerun.core.content import PACKS_DIR, ContentError, load_content


@pytest.fixture
def pack(tmp_path):
    """A writable copy of the Marrow pack."""
    shutil.copytree(PACKS_DIR / "marrow", tmp_path / "copy")
    return tmp_path


def edit_json(path, change):
    data = json.loads(path.read_text())
    change(data)
    path.write_text(json.dumps(data))


def test_marrow_loads(content):
    assert content.world.width == 58 and content.world.height == 18
    assert len(content.npcs) == 6
    assert content.facts and content.dialogue


def test_missing_file_names_the_file(pack):
    (pack / "copy" / "facts.json").unlink()
    with pytest.raises(ContentError) as err:
        load_content("copy", pack)
    assert err.value.file == "facts.json"


def test_broken_json_reports_line(pack):
    (pack / "copy" / "npcs.json").write_text('[{"id": "x",,}]')
    with pytest.raises(ContentError) as err:
        load_content("copy", pack)
    assert err.value.file == "npcs.json" and "line 1" in str(err.value)


def test_ragged_map_rejected(pack):
    path = pack / "copy" / "map.txt"
    path.write_text(path.read_text() + "short\n")
    with pytest.raises(ContentError) as err:
        load_content("copy", pack)
    assert "different widths" in str(err.value)


def test_typo_in_condition_rejected(pack):
    def typo(d):
        d["vera"]["topics"][0]["requires"] = {"factz": ["gauge_reading"]}
    edit_json(pack / "copy" / "dialogue.json", typo)
    with pytest.raises(ContentError) as err:
        load_content("copy", pack)
    assert "unknown condition 'factz'" in str(err.value)


def test_unknown_fact_reference_rejected(pack):
    def bad(d):
        d["kai"]["topics"][0]["replies"][0]["effects"] = [{"learn": "no_such_fact"}]
    edit_json(pack / "copy" / "dialogue.json", bad)
    with pytest.raises(ContentError) as err:
        load_content("copy", pack)
    assert "no_such_fact" in str(err.value)


def test_unknown_place_in_schedule_rejected(pack):
    edit_json(pack / "copy" / "npcs.json", lambda d: d[0]["schedule"][0].update(place="moon"))
    with pytest.raises(ContentError) as err:
        load_content("copy", pack)
    assert err.value.file == "npcs.json"


def test_missing_pack_folder(tmp_path):
    with pytest.raises(ContentError):
        load_content("nope", tmp_path)
