from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Generic, Iterable, List, Optional, Self, Type, TypeVar, overload

from aind_behavior_experiment_launcher.launcher import BaseLauncher

from ._base import IService

logger = logging.getLogger(__name__)

TService = TypeVar("TService", bound=IService)
TLauncher = TypeVar("TLauncher", bound=BaseLauncher)


class ServiceFactory(Generic[TService]):
    @overload
    def __init__(self, service_or_factory: TService) -> None: ...

    @overload
    def __init__(self, service_or_factory: Callable[[BaseLauncher], TService]) -> None: ...

    def __init__(self, service_or_factory: Callable[[BaseLauncher], TService] | TService) -> None:
        self._service_factory: Optional[Callable[[BaseLauncher], TService]] = None
        self._service: Optional[TService] = None
        if callable(service_or_factory):
            self._service_factory = service_or_factory
            self._service = None
        elif isinstance(service_or_factory, IService):
            self._service = service_or_factory
            self._service_factory = None
        else:
            raise ValueError("service_or_factory must be either a service or a service factory")

    def build(self, launcher: BaseLauncher, *args, **kwargs) -> TService:
        if self._service is None:
            if self._service_factory is None:
                raise ValueError("Service factory is not set")
            else:
                self._service = self._service_factory(launcher, *args, **kwargs)
        return self._service

    @property
    def service(self) -> Optional[TService]:
        return self._service


class ServicesFactoryManager:
    _services: Dict[str, ServiceFactory]

    def __init__(
        self,
        launcher: Optional[BaseLauncher] = None,
        *args,
        **kwargs,
    ) -> None:
        self._launcher_reference = launcher

    def __getitem__(self, name: str) -> IService:
        return self._services[name].build(self.launcher)

    def try_get_service(self, name: str) -> Optional[IService]:
        return self._services[name].build(self.launcher)

    def add_service(self, name: str, service_factory: ServiceFactory) -> Self:
        if name in self._services:
            raise IndexError(f"Service with name {name} is already registered")
        self._services[name] = service_factory
        return self

    def remove_service(self, name: str) -> Self:
        if name in self._services:
            self._services.pop(name)
        else:
            raise IndexError(f"Service with name {name} is not registered")
        return self

    def register_launcher(self, launcher: BaseLauncher) -> Self:
        if self._launcher_reference is None:
            self._launcher_reference = launcher
        else:
            raise ValueError("Launcher is already registered")
        return self

    @property
    def launcher(self) -> BaseLauncher:
        if self._launcher_reference is None:
            raise ValueError("Launcher is not registered")
        return self._launcher_reference

    @property
    def services(self) -> Iterable[IService]:
        yield from (service.build(self.launcher) for service in self._services.values())

    def get_services_of_type(self, service_type: Type[TService]) -> Iterable[TService]:
        yield from (service for service in self.services if isinstance(service, service_type))

    def map(self, delegate: Callable[[IService], Any]) -> List[Any]:
        return [delegate(service) for service in self.services]
