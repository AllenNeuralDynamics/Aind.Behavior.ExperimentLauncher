from __future__ import annotations

import importlib.util

if importlib.util.find_spec("magicgui") is None:
    raise ImportError(
        "The 'magicgui' package is required to use this module. "
        "Install the optional dependencies defined in `project.toml` "
        "by running `pip install .[magicgui]`"
    )


from functools import partial
from typing import Any, Iterable, Optional, Type

from magicgui import event_loop
from magicgui.types import Undefined
from magicgui.widgets import (
    Button,
    CheckBox,
    Container,
    Textarea,
    create_widget,
)
from magicgui.widgets.bases import ValueWidget
from pydantic import BaseModel, TypeAdapter, ValidationError
from pydantic.fields import FieldInfo, PydanticUndefined


class _ValidationErrorSink:
    def __init__(self, widget: Optional[ValueWidget] = None):
        self._widget = widget
        self._error: Optional[Exception] = None
        self.clear()

    def __call__(self, e: Exception | None):
        self.update(e)

    @property
    def widget(self) -> Optional[ValueWidget]:
        return self._widget

    @property
    def error(self) -> Optional[Exception]:
        return self._error

    def update(self, e: Exception | None):
        self._error = e
        if self._widget is not None:
            self._widget.value = f"{self.error}"

    def clear(self):
        self.update(None)

    def register_widget(self, widget: ValueWidget):
        self._widget = widget


def _container_updater(container, validator, error_sink: Optional[_ValidationErrorSink] = None):
    # https://icon-sets.iconify.design/material-symbols/

    null_checkbox: CheckBox = container[0]
    input_widget: ValueWidget = container[1]
    validation_button: Button = container[2]
    if error_sink is None:
        error_sink = _ValidationErrorSink()

    is_null = null_checkbox.value
    with input_widget.changed.blocked():
        input_widget.enabled = not is_null
        try:
            if is_null:
                value = None
            else:
                value = input_widget.value

            value = validator(value)
            if value is not None:
                # in case the type adapter does something fancy
                input_widget.set_value(value)

            validation_button.set_icon("material-symbols:check-circle-outline-rounded", "#0b7500")
            error_sink.clear()
        except ValidationError as e:
            validation_button.set_icon("material-symbols:cancel", "#fd0000")
            error_sink(e)


def _make_widget_from_field(
    field: FieldInfo,
    name: str,
    default: Any = Undefined,
    *,
    override_type: Optional[dict[str, Type[ValueWidget]]] = None,
    validation_error_sink: Optional[_ValidationErrorSink] = None,
) -> Container:
    # Each field will be rendered as:
    # - Left button for nullability
    # - Value input
    # - Right button for validation

    if override_type is None:
        override_type = {}
    widget_type = override_type.get(name, None)

    if default is Undefined:
        default = field.get_default(call_default_factory=True)
        if default is PydanticUndefined or default is None:
            default = Undefined

    container: Container = Container(layout="horizontal")

    container.append(
        CheckBox(
            value=(default is Undefined),
            label="N",
        )
    )
    widget = create_widget(default, field.annotation, name=name, widget_type=widget_type)

    container.append(widget)
    container.append(Button(icon="material-symbols:check-circle-outline-rounded", icon_color="#0b7500", enabled=True))
    container.tooltip = field.description
    validator = TypeAdapter(field.rebuild_annotation()).validate_python
    updater = partial(_container_updater, validator=validator, error_sink=validation_error_sink)
    container.changed.connect(updater)
    updater(container)
    return container


def create_container_from_model(
    model: Type[BaseModel] | BaseModel,
    *,
    include_fields: Optional[Iterable[str]] = None,
    exclude_fields: Optional[Iterable[str]] = None,
    override_type: Optional[dict[str, Type[ValueWidget]]] = None,
    validation_error_sink: Optional[_ValidationErrorSink] = None,
    populate_with_instance: bool = False,
) -> "Container":
    if include_fields is None:
        include_fields = model.model_fields.keys()
    if exclude_fields is None:
        exclude_fields = []

    if populate_with_instance:
        if not isinstance(model, BaseModel):
            raise ValueError("Cannot populate with instance if model is not an instance")

    widgets = [
        _make_widget_from_field(
            field,
            name,
            getattr(model, name) if populate_with_instance else Undefined,
            override_type=override_type,
            validation_error_sink=validation_error_sink,
        )
        for name, field in model.model_fields.items()
        if (name in include_fields) and (name not in exclude_fields)
    ]

    container = Container(widgets=widgets)
    return container


def create_form(
    model: BaseModel | Type[BaseModel],
    *,
    include_fields: Optional[Iterable[str]] = None,
    exclude_fields: Optional[Iterable[str]] = None,
    populate_with_instance: bool = False,
    allow_errors: bool = False,
) -> dict[str, Any]:
    submit_button = Button(text="Submit")
    error_stack = Textarea(enabled=False)
    error_sink = _ValidationErrorSink(error_stack)
    model_widget = create_container_from_model(
        model,
        include_fields=include_fields,
        exclude_fields=exclude_fields,
        validation_error_sink=error_sink,
        populate_with_instance=populate_with_instance,
    )
    container = Container(
        widgets=[
            submit_button,
            model_widget,
            error_stack,
        ]
    )
    submit_button.changed.connect(container.close)
    if isinstance(model, BaseModel):
        container.native.setWindowTitle(model.__class__.__name__)
    else:
        container.native.setWindowTitle(model.__name__)
    with event_loop():
        container.show()

    # TODO
    # This is a big hack, but seems like investing
    # too much time into an event driven solution is not worth it atm
    if not allow_errors and error_sink.error is not None:
        raise error_sink.error

    return {getattr(widget[1], "name"): getattr(widget[1], "value") for widget in model_widget}
