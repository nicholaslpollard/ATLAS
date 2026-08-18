import pytest

from packages.features.feature_registry import FeatureDefinition, FeatureRegistry


def test_feature_registry_rejects_duplicate_names():
    definition = FeatureDefinition(
        name="test_feature",
        family="test",
        version="v1",
        minimum_history_bars=1,
        dependencies=("close",),
    )
    registry = FeatureRegistry((definition,))
    with pytest.raises(ValueError, match="already registered"):
        registry.register(definition)
