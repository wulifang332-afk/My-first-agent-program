import pytest

from analyst_agent.tools import SQLTool


def _write_csv(tmp_path):
    data_path = tmp_path / "sample.csv"
    data_path.write_text("category,value\nA,1\nB,2\n")
    return data_path


def test_rejects_non_select(tmp_path):
    data_path = _write_csv(tmp_path)
    tool = SQLTool(str(data_path))
    with pytest.raises(ValueError):
        tool.run_query("DELETE FROM data")


def test_rejects_semicolon_multi_statement(tmp_path):
    data_path = _write_csv(tmp_path)
    tool = SQLTool(str(data_path))
    with pytest.raises(ValueError):
        tool.run_query("SELECT * FROM data; SELECT * FROM data")


def test_appends_limit_when_missing(tmp_path):
    data_path = _write_csv(tmp_path)
    tool = SQLTool(str(data_path))
    prepared = tool._prepare_query("SELECT * FROM data")
    assert prepared.endswith("LIMIT 200")


def test_clamps_limit_over_max(tmp_path):
    data_path = _write_csv(tmp_path)
    tool = SQLTool(str(data_path))
    prepared = tool._prepare_query("SELECT * FROM data LIMIT 500")
    assert "LIMIT 200" in prepared
