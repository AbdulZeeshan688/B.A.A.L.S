import json

from rerun.persistence.save import SAVE_VERSION, RunData, SaveData, SaveStore, Settings


def test_round_trip(tmp_path):
    store = SaveStore(tmp_path)
    data = SaveData(Settings(color=False, ghost=False), best_loops=3,
                    run=RunData(42, 4, {"gauge_reading": {"loop": 2, "seen": True}}, {"outcomes": ["~", "^"]}, [[1, 2]]))
    assert store.save(data) is None
    loaded, notice = store.load()
    assert notice is None
    assert loaded.settings.color is False and loaded.settings.ghost is False
    assert loaded.best_loops == 3
    assert loaded.run.seed == 42 and loaded.run.loop == 4
    assert loaded.run.notebook["gauge_reading"]["loop"] == 2
    assert not (tmp_path / "save.json.tmp").exists(), "atomic write leaves no temp file"


def test_missing_file_is_a_new_game(tmp_path):
    data, notice = SaveStore(tmp_path / "nowhere").load()
    assert data.run is None and notice is None


def test_corrupt_file_is_moved_aside(tmp_path):
    (tmp_path / "save.json").write_text("{not json!!")
    data, notice = SaveStore(tmp_path).load()
    assert data.run is None
    assert "Starting fresh" in notice
    assert (tmp_path / "save.json.bad").exists()
    assert not (tmp_path / "save.json").exists()


def test_empty_file(tmp_path):
    (tmp_path / "save.json").write_text("")
    data, notice = SaveStore(tmp_path).load()
    assert data.run is None and notice


def test_old_version(tmp_path):
    (tmp_path / "save.json").write_text(json.dumps({"version": 0, "run": None}))
    data, notice = SaveStore(tmp_path).load()
    assert "version" in notice
    assert (tmp_path / "save.json.bad").exists()


def test_damaged_run_and_weird_settings(tmp_path):
    raw = {"version": SAVE_VERSION, "settings": {"color": "yes", "ascii_only": True}, "run": {"seed": "x"}}
    (tmp_path / "save.json").write_text(json.dumps(raw))
    data, notice = SaveStore(tmp_path).load()
    assert data.run is None and "damaged" in notice


def test_settings_tolerate_junk():
    s = Settings.from_dict({"color": "yes", "ascii_only": True, "unknown": 1})
    assert s.color is True and s.ascii_only is True
    assert Settings.from_dict(None) == Settings()


def test_unwritable_folder_reports_instead_of_crashing(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    error = SaveStore(blocker / "sub").save(SaveData())
    assert error and error.startswith("Could not save")


def test_disabled_store_never_writes(tmp_path):
    SaveStore(tmp_path / "x", enabled=False).save(SaveData())
    assert not (tmp_path / "x").exists()
