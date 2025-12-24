# devops_agent/formatters/__init__.py
from .registry import FormatterRegistry, get_registry
from .docker import DockerFormatter
from .k8s import KubernetesFormatter

# Initialize Registry
FormatterRegistry.register(DockerFormatter())
FormatterRegistry.register(KubernetesFormatter())
