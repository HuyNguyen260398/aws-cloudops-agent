import pytest

from cloudops_agent.config import DEFAULT_MODEL_ID, load_settings


def test_defaults():
    s = load_settings({})
    assert s.model_id == DEFAULT_MODEL_ID
    assert s.region == "ap-southeast-1"
    assert s.memory_id is None
    assert s.log_level == "INFO"
    assert s.max_prompt_chars == 10000
    assert s.max_tool_output_chars == 20000


def test_env_overrides():
    s = load_settings(
        {
            "MODEL_ID": "m",
            "AWS_REGION": "us-east-1",
            "MEMORY_ID": "mem-1",
            "LOG_LEVEL": "debug",
            "MAX_PROMPT_CHARS": "50",
        }
    )
    assert (s.model_id, s.region, s.memory_id, s.log_level, s.max_prompt_chars) == (
        "m",
        "us-east-1",
        "mem-1",
        "DEBUG",
        50,
    )


def test_region_falls_back_to_aws_default_region():
    assert load_settings({"AWS_DEFAULT_REGION": "eu-west-1"}).region == "eu-west-1"


def test_blank_memory_id_is_none():
    assert load_settings({"MEMORY_ID": "  "}).memory_id is None


def test_invalid_int_raises():
    with pytest.raises(ValueError):
        load_settings({"MAX_PROMPT_CHARS": "abc"})
