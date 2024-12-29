import logging
import os
from pathlib import Path
from typing import List, Optional, TypeVar

import magicgui
import magicgui.types
from aind_behavior_services.db_utils import SubjectDataBase
from magicgui import widgets as widgets
from magicgui.types import Undefined, _Undefined
from magicgui.widgets.bases import BaseValueWidget

logger = logging.getLogger(__name__)

T = TypeVar("T")


def prompt_pick_file_from_list(
    available_files: list[os.PathLike[str]],
    *,
    allow_manual_input: bool = True,
    prompt: str = "Select a file:",
) -> Optional[os.PathLike[str]]:
    def _force_dst(src: BaseValueWidget, dst: BaseValueWidget):
        with dst.changed.blocked():
            print(dst.get_value())
            dst.set_value(Path(src.get_value()))

    container: widgets.Container = widgets.Container(layout="vertical")

    # Add button to submit
    submit_button = widgets.Button(text="Submit")
    submit_button.changed.connect(container.close)
    container.append(submit_button)

    # Make the picker
    _paths = [Path(x) for x in available_files]
    _path_names = [x.name for x in _paths]
    files = widgets.ComboBox(
        choices=_path_names,
        label=prompt,
    )
    container.append(files)
    file_picker = widgets.FileEdit(
        mode=magicgui.types.FileDialogMode.EXISTING_FILE,
        label="Or provide a file path:",
    )
    container.append(file_picker)
    file_picker.enabled = allow_manual_input

    files.changed.connect(lambda _: _force_dst(files, file_picker))
    file_picker.changed.connect(lambda _: _force_dst(file_picker, files))

    container.native.setWindowTitle(prompt)
    with magicgui.event_loop():
        container.show()

    if files.get_value() is not None:
        return _paths[_path_names.index(files.get_value())]

    _p = file_picker.get_value()
    if isinstance(_p, tuple):
        _p = _p[0]
    return _p


def prompt_pick_from_list(
    values: list[str],
    *,
    prompt: str = "Select an option:",
) -> Optional[str]:
    container: widgets.Container = widgets.Container(layout="vertical")

    # Add button to submit
    submit_button = widgets.Button(text="Submit")
    submit_button.changed.connect(container.close)
    container.append(submit_button)

    # Make the picker
    files = widgets.ComboBox(
        value=values,
        label=prompt,
    )
    container.append(files)
    file_picker = widgets.FileEdit(
        mode=magicgui.types.FileDialogMode.EXISTING_FILE,
        label="Or provide a file path:",
    )
    container.append(file_picker)

    container.native.setWindowTitle(prompt)
    with magicgui.event_loop():
        container.show()

    return files.get_value()


def prompt_yes_no_question(*, prompt: str = "Select one option:") -> Optional[bool]:
    _container_outer: widgets.Container = widgets.Container(layout="vertical")
    _container_inner: widgets.Container = widgets.Container(layout="horizontal")
    print(prompt)
    _p = widgets.Label(value=prompt)

    _w_yes = widgets.Button(value=True, text="Yes")
    _w_no = widgets.Button(value=False, text="No")

    _result: List[Optional[bool]] = [None]
    _w_yes.changed.connect(lambda _: _result.__setitem__(0, True))
    _w_no.changed.connect(lambda _: _result.__setitem__(0, False))

    _w_yes.changed.connect(_container_outer.close)
    _w_no.changed.connect(_container_outer.close)

    _container_inner.append(_w_yes)
    _container_inner.append(_w_no)
    _container_outer.append(_p)
    _container_outer.append(_container_inner)

    _container_outer.native.setWindowTitle(prompt)
    with magicgui.event_loop():
        _container_outer.show()

    return _result[0]


def choose_subject(subject_list: SubjectDataBase) -> Optional[str]:
    def _lock_to_index(index_widget: BaseValueWidget, dst: BaseValueWidget):
        with dst.changed.blocked():
            dst.set_value(index_widget.get_value())

    _subject = list(subject_list.subjects.keys())
    _task_logic = [str(getattr(x, "task_logic_target", None)) for x in subject_list.subjects.values()]
    _choices = [f"{subject} => {task_logic}" for subject, task_logic in zip(_subject, _task_logic)]

    container: widgets.Container = widgets.Container(layout="vertical")
    subjects = widgets.Select(choices=_choices, allow_multiple=False, label="Subject")
    btn = widgets.Button(text="Submit")
    btn.changed.connect(container.close)

    container.append(btn)
    container.append(subjects)

    with magicgui.event_loop():
        container.show()

    v = subjects.get_value()
    if v is None:
        return None
    else:
        return _subject[_choices.index(v[0])]


def prompt_experimenter(
    *, default: List[str] | _Undefined = Undefined, allow_empty_string: bool = True
) -> Optional[List[str]]:
    def _close_if_valid(container: widgets.Container, list_edit: widgets.ListEdit):
        if r := list_edit.get_value():
            if len(r) > 0:
                container.close()

    if default is Undefined:
        default = [""]

    container: widgets.Container = widgets.Container(layout="vertical")
    w_experimenter = widgets.ListEdit(value=default)
    btn = widgets.Button(text="Submit")
    btn.changed.connect(lambda _: _close_if_valid(container, w_experimenter))
    container.append(w_experimenter)
    container.append(btn)

    container.native.setWindowTitle("Enter experimenters: ")
    with magicgui.event_loop():
        container.show()

    experimenter = w_experimenter.get_value()
    if experimenter is None:
        return None
    experimenter = [x.strip() for x in experimenter if x.strip() != ""]
    if len(experimenter) == 0:
        if not allow_empty_string:
            logger.error("Experimenter name is not valid.")
        else:
            return None
    return experimenter
