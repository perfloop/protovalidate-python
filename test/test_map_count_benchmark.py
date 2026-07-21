# Copyright (c) 2023-2026 Buf Technologies, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from protobuf import Message

from .conftest import BACKENDS, make_validator
from .gen.buf.validate.conformance.cases.maps_pb import (
    MapExactIgnore,
    MapKeys,
    MapMax,
    MapMin,
    MapMinMax,
    MapValues,
)
from .gen.buf.validate.conformance.cases.required_field_proto3_pb import (
    RequiredImplicitProto3Map,
)

if TYPE_CHECKING:
    from pytest_benchmark.fixture import BenchmarkFixture

    import protovalidate
    from protovalidate import Violation


ExpectedViolation = tuple[str, str, bool | int]
_MAP_ENTRIES = 1024


@pytest.fixture(scope="module", params=BACKENDS)
def validator(request: pytest.FixtureRequest) -> protovalidate.Validator:
    return make_validator(request.param)


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        pytest.param(
            MapMin(),
            ("map.min_pairs", "map must be at least 2 entries", 2),
            id="min-below",
        ),
        pytest.param(MapMin(val={1: 1.0, 2: 2.0}), None, id="min-at-boundary"),
        pytest.param(
            MapMax(val={1: 1.0, 2: 2.0, 3: 3.0}), None, id="max-at-boundary"
        ),
        pytest.param(
            MapMax(val={1: 1.0, 2: 2.0, 3: 3.0, 4: 4.0}),
            ("map.max_pairs", "map must be at most 3 entries", 3),
            id="max-above",
        ),
        pytest.param(
            MapMinMax(val={"a": True}),
            ("map.min_pairs", "map must be at least 2 entries", 2),
            id="min-max-below",
        ),
        pytest.param(
            MapMinMax(val={"a": True, "b": False, "c": True}),
            None,
            id="min-max-between",
        ),
        pytest.param(
            MapMinMax(
                val={"a": True, "b": False, "c": True, "d": False, "e": True}
            ),
            ("map.max_pairs", "map must be at most 4 entries", 4),
            id="min-max-above",
        ),
        pytest.param(MapExactIgnore(), None, id="ignore-empty"),
        pytest.param(
            MapExactIgnore(val={1: "a", 2: "b"}),
            ("map.min_pairs", "map must be at least 3 entries", 3),
            id="ignore-nonempty",
        ),
        pytest.param(
            RequiredImplicitProto3Map(),
            ("required", "value is required", True),
            id="required-empty",
        ),
        pytest.param(
            RequiredImplicitProto3Map(val={"a": "a"}), None, id="required-at-boundary"
        ),
        pytest.param(
            RequiredImplicitProto3Map(val={"a": "a", "b": "b", "c": "c"}),
            ("map.max_pairs", "map must be at most 2 entries", 2),
            id="required-above",
        ),
    ],
)
@pytest.mark.parametrize("fail_fast", [False, True], ids=["collect", "fail-fast"])
def test_map_count_pair_limits(
    validator: protovalidate.Validator,
    message: Message,
    expected: ExpectedViolation | None,
    *,
    fail_fast: bool,
) -> None:
    violations = validator.collect_violations(message, fail_fast=fail_fast)
    if expected is None:
        assert violations == []
        return

    assert len(violations) == 1
    violation = violations[0]
    rule_id, expected_message, expected_value = expected
    assert violation.proto.rule_id == rule_id
    assert str(violation.proto.message) == expected_message
    assert violation.rule_value == expected_value
    assert violation.field_value == (None if rule_id == "required" else message.val)
    assert [element.field_name for element in violation.proto.field.elements] == ["val"]
    expected_rule_path = ["required"] if rule_id == "required" else rule_id.split(".")
    assert [element.field_name for element in violation.proto.rule.elements] == expected_rule_path


@pytest.mark.parametrize(
    ("message", "rule_id"),
    [
        pytest.param(MapKeys(val={1: "a"}), "sint64.lt", id="key-rule"),
        pytest.param(MapValues(val={"a": "x"}), "string.min_len", id="value-rule"),
    ],
)
def test_map_count_keeps_entry_rules(
    validator: protovalidate.Validator, message: Message, rule_id: str
) -> None:
    violations = validator.collect_violations(message)
    assert [violation.proto.rule_id for violation in violations] == [rule_id]


@pytest.mark.parametrize("backend", BACKENDS)
def test_benchmark_cached_map_min_pairs(
    backend: str, benchmark: BenchmarkFixture
) -> None:
    message = MapMin(
        val={index: float(index + 1) for index in range(_MAP_ENTRIES)}
    )
    cached_validator = make_validator(backend)
    assert cached_validator.collect_violations(message) == []

    violations = benchmark(cached_validator.collect_violations, message)

    assert violations == []
