from __future__ import annotations

from copy import deepcopy

from naia_relay.registry.models import (
    PromptDefinition,
    RegistryMode,
    ResourceDefinition,
    ToolDefinition,
)


class RegistryStore:
    def __init__(self, mode: RegistryMode) -> None:
        self.mode = mode
        self._revision = 0
        self._stale = False
        self._tools: dict[str, ToolDefinition] = {}
        self._resources: dict[str, ResourceDefinition] = {}
        self._prompts: dict[str, PromptDefinition] = {}

    @property
    def revision(self) -> int:
        return self._revision

    @property
    def stale(self) -> bool:
        return self._stale

    def _bump_revision(self) -> int:
        self._revision += 1
        self._stale = False
        return self._revision

    def mark_stale(self) -> None:
        self._stale = True

    def mark_fresh(self) -> None:
        self._stale = False

    def register_tool(self, tool: ToolDefinition) -> int:
        if tool.name in self._tools:
            raise ValueError(f"Duplicate tool name: {tool.name}")
        self._tools[tool.name] = deepcopy(tool)
        return self._bump_revision()

    def deregister_tool(self, name: str) -> int:
        self._tools.pop(name)
        return self._bump_revision()

    def register_resource(self, resource: ResourceDefinition) -> int:
        if resource.uri in self._resources:
            raise ValueError(f"Duplicate resource uri: {resource.uri}")
        self._resources[resource.uri] = deepcopy(resource)
        return self._bump_revision()

    def deregister_resource(self, uri: str) -> int:
        self._resources.pop(uri)
        return self._bump_revision()

    def register_prompt(self, prompt: PromptDefinition) -> int:
        if prompt.name in self._prompts:
            raise ValueError(f"Duplicate prompt name: {prompt.name}")
        self._prompts[prompt.name] = deepcopy(prompt)
        return self._bump_revision()

    def deregister_prompt(self, name: str) -> int:
        self._prompts.pop(name)
        return self._bump_revision()

    def get_tool(self, name: str) -> ToolDefinition | None:
        value = self._tools.get(name)
        return deepcopy(value) if value is not None else None

    def get_resource(self, uri: str) -> ResourceDefinition | None:
        value = self._resources.get(uri)
        return deepcopy(value) if value is not None else None

    def get_prompt(self, name: str) -> PromptDefinition | None:
        value = self._prompts.get(name)
        return deepcopy(value) if value is not None else None

    def snapshot(self) -> dict[str, object]:
        return {
            "revision": self._revision,
            "tools": [deepcopy(tool) for tool in self._tools.values()],
            "resources": [deepcopy(resource) for resource in self._resources.values()],
            "prompts": [deepcopy(prompt) for prompt in self._prompts.values()],
        }

    def replace_from_snapshot(self, snapshot: dict[str, object]) -> None:
        tools = snapshot.get("tools", [])
        resources = snapshot.get("resources", [])
        prompts = snapshot.get("prompts", [])
        revision = snapshot.get("revision", 0)

        self._tools = {
            tool.name: deepcopy(tool)
            for tool in tools
            if isinstance(tool, ToolDefinition)
        }
        self._resources = {
            resource.uri: deepcopy(resource)
            for resource in resources
            if isinstance(resource, ResourceDefinition)
        }
        self._prompts = {
            prompt.name: deepcopy(prompt)
            for prompt in prompts
            if isinstance(prompt, PromptDefinition)
        }
        self._revision = int(revision)
        self._stale = False
