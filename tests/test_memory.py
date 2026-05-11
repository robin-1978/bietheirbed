from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from pc_assistant.context.memory import MemoryItem, UserMemory


class TestMemoryItem:
    def test_create(self):
        item = MemoryItem(key="name", value="Alice", category="identity")
        assert item.key == "name"
        assert item.value == "Alice"
        assert item.category == "identity"
        assert item.confidence == 1.0
        assert item.access_count == 0

    def test_touch(self):
        item = MemoryItem(key="test", value="val")
        item.touch()
        assert item.access_count == 1
        item.touch()
        assert item.access_count == 2

    def test_to_dict_roundtrip(self):
        item = MemoryItem(key="lang", value="Python", category="workflow", confidence=0.9, source="manual")
        item.touch()
        d = item.to_dict()
        restored = MemoryItem.from_dict(d)
        assert restored.key == item.key
        assert restored.value == item.value
        assert restored.category == item.category
        assert restored.confidence == item.confidence
        assert restored.access_count == item.access_count

    def test_confidence_clamped(self):
        item = MemoryItem(key="test", value="val", confidence=2.0)
        assert item.confidence == 1.0
        item2 = MemoryItem(key="test", value="val", confidence=-0.5)
        assert item2.confidence == 0.0


class TestUserMemory:
    def test_store_and_retrieve(self):
        mem = UserMemory(storage_path=tempfile.mktemp(suffix=".json"))
        mem.store("name", "Alice", category="identity")
        item = mem.retrieve("name")
        assert item is not None
        assert item.value == "Alice"

    def test_retrieve_case_insensitive(self):
        mem = UserMemory(storage_path=tempfile.mktemp(suffix=".json"))
        mem.store("Name", "Alice")
        item = mem.retrieve("name")
        assert item is not None
        assert item.value == "Alice"

    def test_retrieve_nonexistent(self):
        mem = UserMemory(storage_path=tempfile.mktemp(suffix=".json"))
        assert mem.retrieve("nonexistent") is None

    def test_store_updates_existing(self):
        mem = UserMemory(storage_path=tempfile.mktemp(suffix=".json"))
        mem.store("name", "Alice")
        mem.store("name", "Bob")
        item = mem.retrieve("name")
        assert item is not None
        assert item.value == "Bob"
        assert item.access_count >= 1

    def test_delete(self):
        mem = UserMemory(storage_path=tempfile.mktemp(suffix=".json"))
        mem.store("name", "Alice")
        assert mem.delete("name") is True
        assert mem.retrieve("name") is None

    def test_delete_nonexistent(self):
        mem = UserMemory(storage_path=tempfile.mktemp(suffix=".json"))
        assert mem.delete("nonexistent") is False

    def test_clear(self):
        mem = UserMemory(storage_path=tempfile.mktemp(suffix=".json"))
        mem.store("a", "1")
        mem.store("b", "2")
        mem.clear()
        assert len(mem) == 0

    def test_get_by_category(self):
        mem = UserMemory(storage_path=tempfile.mktemp(suffix=".json"))
        mem.store("name", "Alice", category="identity")
        mem.store("lang", "Python", category="workflow")
        mem.store("city", "Shanghai", category="location")
        identity = mem.get_by_category("identity")
        assert len(identity) == 1
        assert identity[0].value == "Alice"

    def test_get_all(self):
        mem = UserMemory(storage_path=tempfile.mktemp(suffix=".json"))
        mem.store("a", "1")
        mem.store("b", "2")
        assert len(mem.get_all()) == 2

    def test_search(self):
        mem = UserMemory(storage_path=tempfile.mktemp(suffix=".json"))
        mem.store("preference:dark mode", "dark mode", category="preference")
        mem.store("workflow:python", "Python", category="workflow")
        results = mem.search("python")
        assert len(results) >= 1
        assert any("Python" in r.value for r in results)

    def test_persistence(self):
        path = tempfile.mktemp(suffix=".json")
        mem = UserMemory(storage_path=path)
        mem.store("name", "Alice", category="identity")
        mem.save()

        mem2 = UserMemory(storage_path=path)
        item = mem2.retrieve("name")
        assert item is not None
        assert item.value == "Alice"

    def test_build_context_string_empty(self):
        mem = UserMemory(storage_path=tempfile.mktemp(suffix=".json"))
        assert mem.build_context_string() == ""

    def test_build_context_string_with_items(self):
        mem = UserMemory(storage_path=tempfile.mktemp(suffix=".json"))
        mem.store("name", "Alice", category="identity")
        mem.store("lang", "Python", category="workflow")
        ctx = mem.build_context_string()
        assert "User Profile" in ctx
        assert "Alice" in ctx
        assert "Python" in ctx


class TestMemoryExtraction:
    def test_extract_preference(self):
        mem = UserMemory(storage_path=tempfile.mktemp(suffix=".json"))
        extracted = mem.extract_from_text("I prefer dark mode")
        assert len(extracted) >= 1
        assert any("dark mode" in e[1] for e in extracted)

    def test_extract_identity(self):
        mem = UserMemory(storage_path=tempfile.mktemp(suffix=".json"))
        extracted = mem.extract_from_text("My name is Alice")
        assert len(extracted) >= 1
        assert any("alice" in e[1].lower() for e in extracted)

    def test_extract_location(self):
        mem = UserMemory(storage_path=tempfile.mktemp(suffix=".json"))
        extracted = mem.extract_from_text("I live in Shanghai")
        assert len(extracted) >= 1
        assert any("shanghai" in e[1].lower() for e in extracted)

    def test_extract_workflow(self):
        mem = UserMemory(storage_path=tempfile.mktemp(suffix=".json"))
        extracted = mem.extract_from_text("I use Python and Rust")
        assert len(extracted) >= 1

    def test_extract_no_match(self):
        mem = UserMemory(storage_path=tempfile.mktemp(suffix=".json"))
        extracted = mem.extract_from_text("What is the weather today?")
        assert len(extracted) == 0

    def test_extract_and_store_integration(self):
        mem = UserMemory(storage_path=tempfile.mktemp(suffix=".json"))
        extracted = mem.extract_from_text("I prefer dark mode in my editor")
        for key, value, category, source in extracted:
            mem.store(key, value, category=category, source=source)
        assert len(mem) >= 1
        ctx = mem.build_context_string()
        assert "dark mode" in ctx.lower()
