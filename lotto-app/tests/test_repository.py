import json

from data import repository


def test_load_dataset_returns_empty_when_file_missing(tmp_path, monkeypatch):
    missing_file = tmp_path / "does_not_exist.json"
    monkeypatch.setattr(repository, "DATA_FILE", missing_file)

    assert repository.load_dataset() == {"numbers": []}


def test_save_and_load_dataset_round_trip(tmp_path, monkeypatch):
    data_file = tmp_path / "numbers.json"
    monkeypatch.setattr(repository, "DATA_FILE", data_file)

    dataset = {"numbers": [[1, 2, 3, 4, 5, 6]]}
    repository.save_dataset(dataset)

    assert json.loads(data_file.read_text(encoding="utf-8")) == dataset
    assert repository.load_dataset() == dataset


def test_load_draws_extracts_numbers_list(tmp_path, monkeypatch):
    data_file = tmp_path / "numbers.json"
    data_file.write_text(json.dumps({"numbers": [[1, 2, 3, 4, 5, 6]]}), encoding="utf-8")
    monkeypatch.setattr(repository, "DATA_FILE", data_file)

    assert repository.load_draws() == [[1, 2, 3, 4, 5, 6]]
