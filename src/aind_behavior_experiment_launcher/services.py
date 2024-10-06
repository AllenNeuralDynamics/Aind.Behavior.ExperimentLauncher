import logging
from typing import Optional, TypeVar, Union

from .apps import app_service
from .data_mappers import data_mapper_service
from .data_transfer import data_transfer_service
from .resource_monitor import resource_monitor_service

logger = logging.getLogger(__name__)

SupportedServices = Union[
    data_transfer_service.DataTransferService,
    resource_monitor_service.ResourceMonitor,
    app_service.BonsaiApp,
    data_mapper_service.DataMapperService,
]

TService = TypeVar("TService", bound=SupportedServices)


class Services:
    # todo: this could be made more generic and to allow extension/scoping of services
    _data_transfer: Optional[data_transfer_service.DataTransferService]
    _resource_monitor: Optional[resource_monitor_service.ResourceMonitor]
    _app: Optional[app_service.BonsaiApp]
    _data_mapper: Optional[data_mapper_service.DataMapperService]

    def __init__(
        self,
        *args,
        data_transfer: Optional[data_transfer_service.DataTransferService] = None,
        resource_monitor: Optional[resource_monitor_service.ResourceMonitor] = None,
        app: Optional[app_service.BonsaiApp] = None,
        data_mapper: Optional[data_mapper_service.DataMapperService] = None,
        **kwargs,
    ) -> None:
        self._data_transfer = data_transfer
        self._resource_monitor = resource_monitor
        self._app = app
        self._data_mapper = data_mapper

    @property
    def data_transfer(self) -> Optional[data_transfer_service.DataTransferService]:
        return self._data_transfer

    @property
    def resource_monitor(self) -> Optional[resource_monitor_service.ResourceMonitor]:
        return self._resource_monitor

    @property
    def app(self) -> Optional[app_service.BonsaiApp]:
        return self._app

    @property
    def data_mapper(self) -> Optional[data_mapper_service.DataMapperService]:
        return self._data_mapper

    def validate_service(self, obj: Optional[TService]) -> bool:
        if obj is None:
            raise ValueError("Service not set")
        return obj.validate()
