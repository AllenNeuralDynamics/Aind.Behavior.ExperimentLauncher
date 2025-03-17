import logging
from typing import List, Optional, TypeVar

import magicgui
import magicgui.types
from magicgui import widgets as widgets
from qtpy.QtCore import Qt
from typing_extensions import override

from aind_behavior_experiment_launcher.ui import UiHelper

logger = logging.getLogger(__name__)

T = TypeVar("T")


class GuiHelper(UiHelper):
    def prompt_pick_from_list(
        self, value: List[str], prompt: str, allow_0_as_none: bool = True, **kwargs
    ) -> Optional[str]:
        container: widgets.Container = widgets.Container(layout="vertical")

        # Add button to submit
        submit_button = widgets.Button(text="Submit")
        submit_button.changed.connect(container.close)
        container.append(submit_button)

        # Make the picker
        files = widgets.ComboBox(
            value=None if allow_0_as_none else value[0],
            choices=[None] + value if allow_0_as_none else value,
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

    @override
    def prompt_yes_no_question(self, prompt: str) -> bool:
        _container_outer: widgets.Container = widgets.Container(layout="vertical")
        _container_inner: widgets.Container = widgets.Container(layout="horizontal")
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

        if _result[0] is None:
            return False

        return _result[0]

    def prompt_text(self, prompt: str) -> str:
        container: widgets.Container = widgets.Container(layout="vertical")

        # Add button to submit
        submit_button = widgets.Button(text="Submit")
        submit_button.changed.connect(container.close)
        container.append(submit_button)

        # Make the picker
        notes_ui = widgets.TextEdit()
        container.append(notes_ui)
        container.native.setWindowTitle(f"{prompt}")

        with magicgui.event_loop():
            container.show()

        return notes_ui.get_value()


def make_header() -> None:
    _HEADER = """\n
     ██████╗██╗      █████╗ ██████╗ ███████╗
    ██╔════╝██║     ██╔══██╗██╔══██╗██╔════╝
    ██║     ██║     ███████║██████╔╝█████╗
    ██║     ██║     ██╔══██║██╔══██╗██╔══╝
    ╚██████╗███████╗██║  ██║██████╔╝███████╗
     ╚═════╝╚══════╝╚═╝  ╚═╝╚═════╝ ╚══════╝
    """

    sub_text = """
    Command-line-interface Launcher for AIND Behavior Experiments
    Press Control+C to exit at any time.
    """

    container = widgets.Container()
    text_ui = widgets.Label(value=_HEADER)
    text_ui.native.setTextFormat(Qt.TextFormat.MarkdownText)
    font = text_ui.native.font()
    font.setPointSize(15)
    font.setFamily("Courier New")
    text_ui.native.setFont(font)
    sub_text_ui = widgets.Label(value=sub_text)
    ok_ui = widgets.Button(text="Close")
    container.append(text_ui)
    container.append(sub_text_ui)
    container.append(ok_ui)
    ok_ui.clicked.connect(container.close)

    container.native.setWindowTitle("CLABE")
    with magicgui.event_loop():
        container.show()
