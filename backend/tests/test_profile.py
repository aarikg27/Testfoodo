import pytest
from pydantic import ValidationError

from app.schemas import BodyProfile, PreferenceUpdate


def test_body_profile_accepts_personalization_inputs():
    profile = BodyProfile(
        age=20,
        height_cm=175,
        weight_kg=72,
        gender="nonbinary",
        activity_level="moderate",
        goal_type="maintain",
    )

    payload = PreferenceUpdate(profile=profile)
    assert payload.profile.height_cm == 175
    assert payload.profile.use_profile_targets is True


def test_body_profile_rejects_unsafe_or_implausible_ranges():
    with pytest.raises(ValidationError):
        BodyProfile(age=8, height_cm=90, weight_kg=10)
