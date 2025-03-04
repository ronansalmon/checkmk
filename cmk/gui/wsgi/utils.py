#!/usr/bin/env python3
# Copyright (C) 2022 tribe29 GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.
from __future__ import annotations

import typing as t

T = t.TypeVar("T")
Self = t.TypeVar("Self", bound="dict_property")
Inst = dict[str, t.Any]


class dict_property(t.Generic[T]):
    """A typed property (descriptor) which can be used on dict subclasses to type individual keys.

    NOTE:
        This construct is only there to type some aspects of Flask's SessionMixin classes! Don't
        rely on it. Also, it's lacking in some areas (no TypedDict), but this is a necessary
        tradeoff for this use-case.

    Examples:

        >>> class Foo(dict):
        ...     int_key = dict_property[int]()

        It's a real dict:

            >>> foo = Foo()
            >>> foo["bar"] = "is still allowed"  # not type-checked

        But this is typed:

            >>> foo.int_key = 5   # type-checked
            >>> foo.int_key  # also type-checked
            5

        It's in the dict.

            >>> foo["int_key"]  # not type-checked
            5

    """

    def __set_name__(self: Self, owner: Inst, name: str) -> None:
        self.name: str = name

    def __set__(self: Self, instance: Inst, value: T) -> None:
        instance[self.name] = value

    @t.overload
    def __get__(self: Self, instance: None, owner: None = None) -> dict_property[T]:
        ...

    @t.overload
    def __get__(self: Self, instance: Inst, owner: type[dict] = ...) -> T:
        ...

    def __get__(
        self: Self, instance: Inst | None, owner: type[dict] | None = None
    ) -> dict_property[T] | T:
        if instance is None:
            return self
        try:
            return instance[self.name]
        except KeyError as exc:
            raise AttributeError(exc) from exc

    def __delete__(self: Self, instance: Inst) -> None:
        try:
            del instance[self.name]
        except KeyError as exc:
            raise AttributeError(exc) from exc
