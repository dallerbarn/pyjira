from __future__ import annotations

import asyncio
import re
from typing import Optional

from prompt_toolkit import HTML
from prompt_toolkit.application import Application
from prompt_toolkit.application.current import get_app
from prompt_toolkit.formatted_text import AnyFormattedText, StyleAndTextTuples, to_formatted_text
from prompt_toolkit.layout import Layout
from prompt_toolkit.layout.containers import AnyContainer
from prompt_toolkit.styles import BaseStyle

from pyjira.client import JiraIssue
from pyjira.color import hex_to_hls, hls_to_hex


async def print_container(container: AnyContainer, style: Optional[BaseStyle]):
    def exit_immediately() -> None:
        asyncio.get_event_loop().call_soon(lambda: get_app().exit(result=''))

    application = Application(
        layout=Layout(container=container),
        mouse_support=False,
        style=style,
        full_screen=False,

    )

    await application.run_async(pre_run=exit_immediately())


def text_max_length(text: str, max: int) -> str:
    if len(text) > max:
        return f"{text[:max-3]}..."
    return text


def html_formatted_text(text: str) -> AnyFormattedText:
    formatted = text.replace('\r\n', '\n')
    matches = re.finditer(r"color=\"(#[1-9a-f]{6})\"", formatted)
    for match in matches:
        hex_color = match.group(1)
        h, l, s = hex_to_hls(hex_color)
        l = max(l, 80)
        formatted = formatted.replace(hex_color, hls_to_hex((h,l,s)))
    return HTML(formatted)


def issue_id_render(issue: JiraIssue) -> StyleAndTextTuples:
    result: StyleAndTextTuples = []
    if issue.parent:
        result.extend(
            to_formatted_text(issue.parent.id, style=f"class:issue_id.{issue.parent.issue_type.split()[0].lower()}"))
        result.extend(to_formatted_text(" / ", style="class:issue"))

    result.extend(to_formatted_text(issue.id, style=f"class:issue_id.{issue.issue_type.split()[0].lower()}"))
    return result


def issue_summary_render(issue: JiraIssue) -> StyleAndTextTuples:
    result: StyleAndTextTuples = []
    result.extend(to_formatted_text(issue.summary, style="class:issue"))
    return result


def summary_render(issue: JiraIssue) -> StyleAndTextTuples:
    result: StyleAndTextTuples = issue_id_render(issue)
    result.extend(to_formatted_text(f" {issue.status.name}", style="class:issue.status"))
    if issue.subtasks:
        result.extend(to_formatted_text(" ", style="class:issue"))
        result.extend(to_formatted_text(f"subtasks[{len(issue.subtasks)}]", style="class:issue.subtasks"))

    result.extend(to_formatted_text(" ", style="class:issue"))
    result.extend(issue_summary_render(issue))
    return result
