import pytest

from naia_relay.registry import PromptDefinition, RegistryStore, ResourceDefinition, ToolDefinition


def test_registry_store_tracks_revision_increments() -> None:
    store = RegistryStore(mode="authoritative")

    revision_1 = store.register_tool(
        ToolDefinition(name="demo", description="Demo tool", input_schema={})
    )
    revision_2 = store.register_resource(ResourceDefinition(uri="file:///demo", name="demo"))
    revision_3 = store.register_prompt(PromptDefinition(name="prompt", description="Prompt"))

    assert (revision_1, revision_2, revision_3) == (1, 2, 3)


def test_registry_store_rejects_duplicate_names_and_uris() -> None:
    store = RegistryStore(mode="authoritative")
    store.register_tool(ToolDefinition(name="demo", description="Demo tool", input_schema={}))
    store.register_resource(ResourceDefinition(uri="file:///demo", name="demo"))
    store.register_prompt(PromptDefinition(name="prompt", description="Prompt"))

    with pytest.raises(ValueError):
        store.register_tool(ToolDefinition(name="demo", description="Again", input_schema={}))

    with pytest.raises(ValueError):
        store.register_resource(ResourceDefinition(uri="file:///demo", name="again"))

    with pytest.raises(ValueError):
        store.register_prompt(PromptDefinition(name="prompt", description="Again"))


def test_registry_store_can_rebuild_mirrored_state_from_snapshot() -> None:
    authoritative = RegistryStore(mode="authoritative")
    authoritative.register_tool(
        ToolDefinition(name="demo", description="Demo tool", input_schema={})
    )
    authoritative.register_resource(ResourceDefinition(uri="file:///demo", name="demo"))
    authoritative.register_prompt(PromptDefinition(name="prompt", description="Prompt"))

    mirrored = RegistryStore(mode="mirrored")
    mirrored.replace_from_snapshot(authoritative.snapshot())

    assert mirrored.revision == authoritative.revision
    assert mirrored.get_tool("demo") is not None
    assert mirrored.get_resource("file:///demo") is not None
    assert mirrored.get_prompt("prompt") is not None
