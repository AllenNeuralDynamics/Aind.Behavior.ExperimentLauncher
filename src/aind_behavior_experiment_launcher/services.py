from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Generic, Iterable, List, Optional, Self, Type, TypeVar, overload

from ._base import IService
from .launcher import Launcher

logger = logging.getLogger(__name__)

TService = TypeVar("TService", bound=IService)


class ServiceBuilder(Generic[TService]):
    @overload
    def __init__(self, service_or_builder: TService) -> None: ...

    @overload
    def __init__(self, service_or_builder: Callable[[Launcher], TService]) -> None: ...

    def __init__(self, service_or_builder: Callable[[Launcher], TService] | TService) -> None:
        self._service_builder: Optional[Callable[[Launcher], TService]] = None
        self._service: Optional[TService] = None
        if callable(service_or_builder):
            self._service_builder = service_or_builder
            self._service = None
        elif isinstance(service_or_builder, IService):
            self._service = service_or_builder
            self._service_builder = None
        else:
            raise ValueError("service_or_builder must be either a service or a service builder")

    def build(self, launcher: Launcher, *args, **kwargs) -> TService:
        if self._service is None:
            if self._service_builder is None:
                raise ValueError("Service builder is not set")
            else:
                self._service = self._service_builder(launcher, *args, **kwargs)
        return self._service

    @property
    def service(self) -> Optional[TService]:
        return self._service


class ServicesBuilderManager:
    _services: Dict[str, ServiceBuilder]

    def __init__(
        self,
        launcher: Optional[Launcher] = None,
        *args,
        **kwargs,
    ) -> None:
        self._launcher_reference = launcher

    def __getitem__(self, name: str) -> IService:
        return self._services[name].build(self.launcher)

    def try_get_service(self, name: str) -> Optional[IService]:
        return self._services[name].build(self.launcher)

    def add_service(self, name: str, service_builder: ServiceBuilder) -> Self:
        self._services[name] = service_builder
        return self

    def remove_service(self, name: str) -> Self:
        self._services.pop(name)
        return self

    def register_launcher(self, launcher: Launcher) -> Self:
        if self._launcher_reference is None:
            self._launcher_reference = launcher
        else:
            raise ValueError("Launcher is already registered")
        return self

    @property
    def launcher(self) -> Launcher:
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
