from website_analyzer.apis.analyzer import ApiAnalyzer


def test_schema_inference_for_json(tmp_path) -> None:
    response = tmp_path / "response.json"
    response.write_text('{"id": 1, "name": "test"}', encoding="utf-8")
    schema = ApiAnalyzer._schema_from_response(response)
    assert schema["type"] == "object"
    assert schema["properties"]["id"]["type"] == "int"
