from __future__ import annotations

from dataclasses import dataclass, field
from functools import partial
from typing import Generic, Generator
from typing import List, Optional, TypeVar

from prompt_toolkit.filters import Condition
from prompt_toolkit.formatted_text import AnyFormattedText
from prompt_toolkit.formatted_text import StyleAndTextTuples
from prompt_toolkit.formatted_text import Template
from prompt_toolkit.formatted_text import to_formatted_text
from prompt_toolkit.key_binding.key_bindings import KeyBindings, merge_key_bindings
from prompt_toolkit.key_binding.key_processor import KeyPressEvent
from prompt_toolkit.layout.containers import AnyContainer, HSplit, VSplit
from prompt_toolkit.layout.containers import ConditionalContainer, DynamicContainer
from prompt_toolkit.layout.containers import Container, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.dimension import AnyDimension
from prompt_toolkit.layout.margins import ConditionalMargin, ScrollbarMargin
from prompt_toolkit.mouse_events import MouseEvent, MouseEventType
from prompt_toolkit.widgets import Box
from prompt_toolkit.widgets import Label
from prompt_toolkit.widgets.base import Border

from pyjira.client import JiraIssue, JiraComment, DevStatus
from pyjira.render import issue_summary_render, issue_id_render, html_formatted_text, text_max_length


def _intersperse(lst: List, item) -> List:
    result = [item] * (len(lst) * 2 - 1)
    result[0::2] = lst
    return result


def build_issue_container(issue: JiraIssue) -> AnyContainer:
    text = issue_summary_render(issue)
    if issue.assignee:
        text.extend(to_formatted_text("\nAssignee: ", style="class:dull"))
        text.extend(to_formatted_text(issue.assignee.name, style="class:issue.assignee"))
    if issue.creator:
        text.extend(to_formatted_text(" Creator: ", style="class:dull"))
        text.extend(to_formatted_text(issue.creator.name, style="class:issue.assignee"))

    description = issue.description.replace('\r\n', '')

    return FrameLeftTitle(Box(HSplit([
        Label(to_formatted_text(issue.status.name, style="class:issue.status")),
        Label(text),
        Window(
            content=FormattedTextControl(html_formatted_text(description)),
            wrap_lines=True
        )
    ]), padding=1), title=issue_id_render(issue))


def build_subtasks_container(issue: JiraIssue) -> AnyContainer:
    subtask_containers = []
    for subtask in issue.subtasks:
        subtask_containers.append(
            VSplit([
                Label(to_formatted_text(text_max_length(subtask.summary, 50), style="class:issue"), width=50),
                Box(Label(issue_id_render(subtask), width=8), padding=0, padding_left=1),
                Box(Label(to_formatted_text(subtask.status.name, style="class:dull"), width=10), padding=0, padding_left=1),  # TODO style
                Label(to_formatted_text("Unassigned" if issue.assignee is None else issue.assignee.name,
                                        style="class:issue.assignee"))
            ])
        )

    fill = partial(Window, style="class:dull")
    return FrameLeftTitle(
        Box(
            HSplit(
                _intersperse(subtask_containers,
                             VSplit([fill(char="\u2500"), Label("\u2500", style="class:dull", dont_extend_width=True)]))
            ),
            padding=1
        ),
        title=to_formatted_text("Sub-Tasks", style="class:comments"))  # TODO style


def build_comments_container(comments: List[JiraComment]) -> AnyContainer:
    comment_containers = []
    for comment in comments:
        text = []
        text.extend(to_formatted_text(comment.author.name, style="class:comment.author"))
        text.extend(to_formatted_text(" ", style="class:comment"))
        text.extend(to_formatted_text(comment.updated, style="class:comment.date"))
        comment_containers.append(Label(text))
        comment_containers.append(Box(
            Window(
                content=FormattedTextControl(to_formatted_text(comment.body, style="class:comment.body")),
                wrap_lines=True
            )
            , padding_left=2, padding_bottom=1))

    return FrameLeftTitle(Box(HSplit(comment_containers), padding_top=1, padding_left=1),
                          title=to_formatted_text("Comments", style="class:comments"))


def build_dev_status_container(dev_status: DevStatus) -> AnyContainer:
    commit_containers = []
    for commit in dev_status.commits:
        commit_containers.append(HSplit([
            VSplit([
                Label(to_formatted_text(commit.id + " ", "class:dev.commit.id"), dont_extend_width=True),
                Label(to_formatted_text(commit.author_name + " ", "class:dev.commit.author"), dont_extend_width=True),
                Label(to_formatted_text(commit.message, "class:dev.commit.message"))
            ]),
            VSplit([

                Label(to_formatted_text(commit.url, "class:dev.commit.url"))
            ])
        ]))
    branch_containers = []
    for branch in dev_status.branches:
        branch_containers.append(
            VSplit([
                Label(to_formatted_text(branch.name, style="class:dev.branch.name"), dont_extend_width=True),
                Box(Label(to_formatted_text(branch.url, style="class:dev.branch.url")), padding=0, padding_left=1)
            ])
        )
    pull_request_containers = []
    for pull_request in dev_status.pull_requests:
        reviewers = to_formatted_text("Reviewer: ", style="class:dull")
        pull_request.reviewers.sort(key=lambda x: f"{'A' if x.approved else 'B'}{x.name}", reverse=False)
        for reviewer in pull_request.reviewers:
            reviewers.extend(to_formatted_text(reviewer.name, style=f"class:dev.pull_request.review.{'approved' if reviewer.approved else 'waiting'}"))
            reviewers.extend(to_formatted_text(" ", style=""))

        user_container = [Label(to_formatted_text("Author: ", style="class:dull"), dont_extend_width=True),
                          Box(Label(to_formatted_text(pull_request.author_name, style="class:dev.pull_request.author")), padding=0, padding_right=1),
                          Label(reviewers),
                          Label("")]

        pull_request_containers.append(
            HSplit([
                VSplit([
                    Label(to_formatted_text(text_max_length(pull_request.name, 60), style="class:dev.pull_request.name"), width=60),
                    Box(Label(to_formatted_text(f" {pull_request.status} ",
                                            style=f"class:dev.pull_request.status.{pull_request.status.lower()}"),
                          width=10), padding=0, padding_left=1, padding_right=1),
                    Label(to_formatted_text(f"Comments: {pull_request.comment_count}",
                                            style="class:dev.pull_request.comment"))
                ]),
                VSplit(user_container),
                Label(pull_request.url, style="class:dull")
            ])
        )

    dev_container = Box(HSplit([
        Label("Commit:"),
        Box(HSplit(_intersperse(commit_containers, Label(""))), padding_bottom=1, padding=0),
        Label("Branch:"),
        Box(HSplit(branch_containers), padding_bottom=1, padding=0),
        Label("Pull request:"),
        HSplit(_intersperse(pull_request_containers, Label("")))
    ]), padding=1)

    return FrameLeftTitle(dev_container, title=to_formatted_text("Development", style="class:comments"))


E = KeyPressEvent


class Drawable:
    def render(self) -> StyleAndTextTuples:
        raise NotImplementedError()


TEV = TypeVar("TEV", bound=Drawable)


@dataclass()
class TreeElement(Generic[TEV]):
    value: TEV
    children: List[TreeElement] = field(default_factory=list)
    expanded: bool = False


class TreeComponent(Generic[TEV]):
    open_character: str = ""
    close_character: str = ""
    container_style: str = ""
    default_style: str = ""
    selected_style: str = ""
    checked_style: str = ""
    show_scrollbar: bool = True
    values: List[TreeElement[TEV]]
    _selected_index: int

    def __init__(self, values: List[TreeElement[TEV]], external_key_bindings: Optional[KeyBindings]) -> None:
        self.set_values(values)
        kb = KeyBindings()

        @kb.add("up")
        def _up(event: E) -> None:
            self._selected_index = max(0, self._selected_index - 1)

        @kb.add("down")
        def _down(event: E) -> None:
            self._selected_index = min(self._number_of_visible_elements() - 1, self._selected_index + 1)

        @kb.add("pageup")
        def _pageup(event: E) -> None:
            w = event.app.layout.current_window
            if w.render_info:
                self._selected_index = max(
                    0, self._selected_index - len(w.render_info.displayed_lines)
                )

        @kb.add("pagedown")
        def _pagedown(event: E) -> None:
            w = event.app.layout.current_window
            if w.render_info:
                self._selected_index = min(
                    self._number_of_visible_elements() - 1,
                    self._selected_index + len(w.render_info.displayed_lines),
                )

        @kb.add("enter")
        @kb.add(" ")
        @kb.add("right")
        def _click(event: E) -> None:
            self._handle_enter()

        merged_bindings = [kb]
        if external_key_bindings:
            merged_bindings.append(external_key_bindings)

        self.control = FormattedTextControl(
            self._get_text_fragments, key_bindings=merge_key_bindings(merged_bindings), focusable=True
        )

        self.window = Window(
            content=self.control,
            style=self.container_style,
            right_margins=[
                ConditionalMargin(
                    margin=ScrollbarMargin(display_arrows=True),
                    filter=Condition(lambda: self.show_scrollbar),
                ),
            ],
            dont_extend_height=True,
        )

    def get_selected_element(self) -> TreeElement[TEV]:
        return self._find_expanded_by_index(self._selected_index)

    def set_values(self, values: List[TreeElement[TEV]]):
        self.values = values
        self._selected_index = 0

    def _number_of_visible_elements(self) -> int:
        return len(list(self._traverse_visible(self.values, 0)))

    def _traverse_visible(self, elements: List[TreeElement[TEV]], level: int) -> Generator[int, TreeElement[TEV]]:
        for e in elements:
            yield level, e
            if e.expanded:
                yield from self._traverse_visible(e.children, level + 1)

    def _find_expanded_by_index(self, i) -> TreeElement[TEV]:
        index = 0
        for _, element in self._traverse_visible(self.values, 0):
            if i == index:
                return element
            index += 1

    def _handle_enter(self) -> None:
        element = self._find_expanded_by_index(self._selected_index)
        element.expanded = not element.expanded

    def _get_text_fragments(self) -> StyleAndTextTuples:
        def mouse_handler(mouse_event: MouseEvent) -> None:
            if mouse_event.event_type == MouseEventType.MOUSE_UP:
                self._selected_index = mouse_event.position.y
                self._handle_enter()

        current_index = 0
        result: StyleAndTextTuples = []
        for level, element in self._traverse_visible(self.values, 0):
            style = ""
            for i in range(level):
                result.append((style, "   "))

            selected = current_index == self._selected_index

            result.append((style, self.open_character))

            if selected:
                result.append(("[SetCursorPosition]", ""))

            if element.children:
                if element.expanded:
                    result.append((style, "-"))
                else:
                    result.append((style, "+"))
            else:
                result.append((style, " "))

            result.append((style, self.close_character))
            result.append((self.default_style, " "))

            result.extend(element.value.render())

            result.append(("", "\n"))
            current_index += 1

        # Add mouse handler to all fragments.
        for i in range(len(result)):
            result[i] = (result[i][0], result[i][1], mouse_handler)

        if len(result) > 0:
            result.pop()  # Remove last newline.
        return result

    def __pt_container__(self) -> Container:
        return self.window


class FrameLeftTitle:

    def __init__(
        self,
        body: AnyContainer,
        title: AnyFormattedText = "",
        style: str = "",
        width: AnyDimension = None,
        height: AnyDimension = None,
        key_bindings: Optional[KeyBindings] = None,
        modal: bool = False,
    ) -> None:

        self.title = title
        self.body = body

        fill = partial(Window, style="class:frame.border")
        style = "class:frame " + style

        top_row_with_title = VSplit(
            [
                fill(width=1, height=1, char=Border.TOP_LEFT),
                fill(width=1, height=1, char="|"),
                Label(
                    lambda: Template(" {} ").format(self.title),
                    style="class:frame.label",
                    dont_extend_width=True,
                ),
                fill(width=1, height=1, char="|"),
                fill(char=Border.HORIZONTAL),
                fill(width=1, height=1, char=Border.TOP_RIGHT),
            ],
            height=1,
        )

        top_row_without_title = VSplit(
            [
                fill(width=1, height=1, char=Border.TOP_LEFT),
                fill(char=Border.HORIZONTAL),
                fill(width=1, height=1, char=Border.TOP_RIGHT),
            ],
            height=1,
        )

        @Condition
        def has_title() -> bool:
            return bool(self.title)

        self.container = HSplit(
            [
                ConditionalContainer(content=top_row_with_title, filter=has_title),
                ConditionalContainer(content=top_row_without_title, filter=~has_title),
                VSplit(
                    [
                        fill(width=1, char=Border.VERTICAL),
                        DynamicContainer(lambda: self.body),
                        fill(width=1, char=Border.VERTICAL),
                    ],
                    padding=0,
                ),
                VSplit(
                    [
                        fill(width=1, height=1, char=Border.BOTTOM_LEFT),
                        fill(char=Border.HORIZONTAL),
                        fill(width=1, height=1, char=Border.BOTTOM_RIGHT),
                    ],
                    height=1,
                ),
            ],
            width=width,
            height=height,
            style=style,
            key_bindings=key_bindings,
            modal=modal,
        )

    def __pt_container__(self) -> Container:
        return self.container

