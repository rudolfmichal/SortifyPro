import json

import pytest

from benchmarks import gil_benchmark as gb
from main import main
from scripts.generate_test_data import generate


def test_generate_test_data_is_deterministic(tmp_path):
    first = generate(tmp_path / "a", seed=1)
    second = generate(tmp_path / "b", seed=1)
    assert len(first) == len(second) > 40
    assert (tmp_path / "a" / "faktura.pdf").read_bytes() == (tmp_path / "b" / "faktura.pdf").read_bytes()


def test_cli_end_to_end(tmp_path, capsys):
    data = tmp_path / "data"
    assert main(["demo-data", str(data)]) == 0
    assert main(["scan", str(data)]) == 0
    assert main(["duplicates", str(data), "--mode", "sequential"]) == 0
    assert "Duplikaty: 9" in capsys.readouterr().out
    assert main(["space", str(data)]) == 0
    assert main(["sort", str(data)]) == 0                   # podgląd - nic nie rusza
    assert (data / "faktura.pdf").exists()
    assert main(["sort", str(data), "--apply"]) == 0
    assert not (data / "faktura.pdf").exists()
    assert main(["undo", "--last"]) == 0
    assert (data / "faktura.pdf").exists()


def test_cli_reports_errors(tmp_path, capsys):
    assert main(["scan", str(tmp_path / "nie_ma")]) == 2
    assert "Błąd" in capsys.readouterr().err


def test_benchmark_tiny_run(tmp_path):
    report = gb.run_benchmark(file_count=2, size_mb=0.05, workers=2, repeats=1)
    assert len(report.rows) == len(gb.SCENARIOS) * 3
    table = gb.format_markdown(report)
    assert "sequential" in table or "sekwencyjnie" in table.lower()
    out = tmp_path / "b.json"
    assert main(["benchmark", "--files", "2", "--size-mb", "0.05",
                 "--repeats", "1", "--json", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["rows"]


def test_benchmark_validates():
    with pytest.raises(ValueError):
        gb.run_benchmark(file_count=0)


def test_write_to_readme_replaces_block(tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text("a\n<!-- BENCHMARK:START -->\nstare\n<!-- BENCHMARK:END -->\nb\n",
                      encoding="utf-8")
    report = gb.run_benchmark(file_count=1, size_mb=0.01, workers=1, repeats=1)
    gb.write_to_readme(report, readme)
    text = readme.read_text(encoding="utf-8")
    assert "stare" not in text and text.startswith("a\n") and text.endswith("b\n")
