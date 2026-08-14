"""integrate.py 单元测试：CLI 校验与参数收集。"""

import pytest

from integrate import collect_user_params, validate_cli

# 精选别名对应的属性名
_CURATED = ["description", "api_base_url", "auth_mode", "with_db",
            "with_redis", "with_child_app", "child_apps", "api_prefix"]


class Args:
    """模拟 parsed args（精简别名默认 None）。"""

    def __init__(self, **kw):
        for k in _CURATED:
            setattr(self, k, None)
        self.combo = None
        self.project = None
        self.frontend = None
        self.backend = None
        self.extra = []
        for k, v in kw.items():
            setattr(self, k, v)


class Parser:
    """模拟 argparse parser：error 抛 SystemExit（argparse 行为）。"""

    def error(self, msg):
        raise SystemExit(msg)


def test_validate_cli_mutex():
    with pytest.raises(SystemExit):
        validate_cli(Parser(), Args(combo="python-react", project="proj",
                                    frontend="x", backend="y"))


def test_validate_cli_pairing_missing_backend():
    with pytest.raises(SystemExit):
        validate_cli(Parser(), Args(combo=None, project="proj", frontend="x"))


def test_validate_cli_pairing_missing_both():
    with pytest.raises(SystemExit):
        validate_cli(Parser(), Args(combo=None, project="proj"))


def test_validate_cli_ok_abbrev():
    validate_cli(Parser(), Args(combo="python-react", project="proj"))  # 不抛


def test_validate_cli_ok_explicit():
    validate_cli(Parser(), Args(combo=None, project="proj", frontend="x", backend="y"))


def test_collect_user_params_curated_and_extra():
    args = Args(combo="python-react", project="proj", auth_mode="opaque",
                extra=["with_taskqueue=none"])
    params = collect_user_params(Parser(), args)
    assert params == {"auth_mode": "opaque", "with_taskqueue": "none"}


def test_collect_user_params_empty():
    params = collect_user_params(Parser(), Args(combo="python-react", project="proj"))
    assert params == {}
