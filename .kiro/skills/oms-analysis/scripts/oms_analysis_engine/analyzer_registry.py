"""Analyzer 注册与发现"""
from __future__ import annotations
import importlib
import pkgutil
from oms_analysis_engine.base import BaseAnalyzer
from oms_analysis_engine.models.request import AnalysisIntent


class AnalyzerRegistry:
    def __init__(self):
        self._analyzers: dict[str, BaseAnalyzer] = {}

    def register(self, analyzer: BaseAnalyzer) -> None:
        self._analyzers[analyzer.intent] = analyzer

    def unregister(self, intent: str) -> None:
        self._analyzers.pop(intent, None)

    def auto_discover(self) -> None:
        import oms_analysis_engine.analyzers as pkg
        for importer, modname, ispkg in pkgutil.iter_modules(pkg.__path__):
            mod = importlib.import_module(f"oms_analysis_engine.analyzers.{modname}")
            for attr_name in dir(mod):
                attr = getattr(mod, attr_name)
                if (isinstance(attr, type)
                        and issubclass(attr, BaseAnalyzer)
                        and attr is not BaseAnalyzer
                        and hasattr(attr, 'intent')
                        and attr.intent):
                    self.register(attr())

    def resolve(self, intents: list[AnalysisIntent]) -> list[BaseAnalyzer]:
        return [self._analyzers[i.intent_type]
                for i in intents
                if i.intent_type in self._analyzers]

    def list_analyzers(self) -> dict[str, str]:
        return {k: v.name for k, v in self._analyzers.items()}
