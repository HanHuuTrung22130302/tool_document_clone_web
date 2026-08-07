from website_analyzer.crawler.interactions import InteractionExplorer


def test_interaction_policy_rejects_side_effect_controls() -> None:
    assert InteractionExplorer.is_safe({"label": "Features", "type": "button", "disabled": False})
    assert not InteractionExplorer.is_safe({"label": "Delete account", "type": "button", "disabled": False})
    assert not InteractionExplorer.is_safe({"label": "Show results", "type": "submit", "disabled": False})
