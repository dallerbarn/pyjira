from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List

import click
import yaml
from aiohttp import BasicAuth
from prompt_toolkit import print_formatted_text
from prompt_toolkit import prompt
from prompt_toolkit.application import Application
from prompt_toolkit.application.current import get_app
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.formatted_text import StyleAndTextTuples
from prompt_toolkit.key_binding import KeyPressEvent
from prompt_toolkit.key_binding.bindings.focus import focus_next, focus_previous
from prompt_toolkit.key_binding.defaults import load_key_bindings
from prompt_toolkit.key_binding.key_bindings import KeyBindings, merge_key_bindings
from prompt_toolkit.layout import Container
from prompt_toolkit.layout import Layout, ScrollablePane
from prompt_toolkit.layout.containers import HSplit, VSplit, AnyContainer
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import TextArea, Label, Frame

from pyjira import background_task
from pyjira.client import JiraClient, JiraIssue, build_detailed_jira_issue
from pyjira.client import build_summary_jira_issue
from pyjira.configuration import Board, Filter, encode
from pyjira.configuration import Config, load_configuration
from pyjira.container import build_issue_container, build_comments_container, build_subtasks_container, \
    build_dev_status_container, TreeComponent, TreeElement, Drawable
from pyjira.render import summary_render, print_container

LOGGER = logging.getLogger("")
LOGGER.setLevel(logging.WARN)
logging.basicConfig(filename="log.txt")

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


class COLOR(Enum):
    WHITE = "#f0f0f0"
    DULL_GREY = "#8a8a8a"
    RED = "#f54242"
    GREEN = "#67eb34"
    BLUE = "#349ceb"
    LIGHT_BLUE = "#34ebeb"
    ORANGE = "#eb8934"
    YELLOW = "#ebe534"
    BLACK = "#000000"


style = Style.from_dict(
    {
        "issue": "",
        "issue.status": COLOR.DULL_GREY.value,
        "issue_id": "bold",
        "issue_id.story": COLOR.GREEN.value,
        "issue_id.sub-task": COLOR.BLUE.value,
        "issue_id.bug": COLOR.RED.value,
        "issue.subtasks": COLOR.DULL_GREY.value,
        "issue.assignee": COLOR.BLUE.value,
        "issue.creator": COLOR.BLUE.value,
        "comments": f"bold {COLOR.LIGHT_BLUE.value}",
        "comment": "",
        "comment.author": COLOR.BLUE.value,
        "comment.date": COLOR.DULL_GREY.value,
        "comment.body": COLOR.WHITE.value,
        "dull": COLOR.DULL_GREY.value,
        "dev.commit.message": COLOR.WHITE.value,
        "dev.commit.author": COLOR.BLUE.value,
        "dev.commit.url": COLOR.DULL_GREY.value,
        "dev.commit.id": COLOR.DULL_GREY.value,
        "dev.branch.name": COLOR.WHITE.value,
        "dev.branch.url": COLOR.DULL_GREY.value,
        "dev.pull_request.review.approved": COLOR.GREEN.value,
        "dev.pull_request.review.waiting": COLOR.DULL_GREY.value,
        "dev.pull_request.author": COLOR.BLUE.value,
        "dev.pull_request.name": COLOR.WHITE.value,
        "dev.pull_request.status.merged": f"bold bg:{COLOR.GREEN.value} {COLOR.BLACK.value}",
        "dev.pull_request.status.declined": f"bold bg:{COLOR.ORANGE.value} {COLOR.BLACK.value}",
        "dev.pull_request.status.open": f"bold bg:{COLOR.WHITE.value} {COLOR.BLACK.value}",
        "dev.pull_request.comment": COLOR.WHITE.value,
    })


@click.group(context_settings=CONTEXT_SETTINGS)
@click.version_option(version='1.0.0')
def pyjira():
    pass


@pyjira.command(help="Configure the cli")
def configure():
    jira_base_url = prompt("Jira base url: ")
    cert_path = prompt("Server cert path: ")
    user = prompt("Jira user: ")
    token = prompt("Jira token: ")
    print_formatted_text(f"""A jira access token can be generated at
        {jira_base_url}/plugins/servlet/no.kantega.kerberosauth.kerberosauth-plugin/user/api-tokens
        """)
    jql = prompt("Optional - Default dashboard jql: ")

    config = Config(
        cert_path=cert_path,
        jira_base_url=jira_base_url,
        user=user,
        token=token,
        board=Board(Filter(jql)))
    file_data = encode(config)

    path = _get_config_path()
    with path.open("w") as file:
        file.write(yaml.dump(file_data))
    print_formatted_text(f"A config file has been created at {str(path)}")


@pyjira.command(help="List all issues assigned to the current user")
@click.option("--open-sprint", "-o", is_flag=True, help="limit to the current sprint")
def ls(open_sprint: bool):
    config = _get_config()

    async def load_issue():
        data: Dict
        async with JiraClient(config, auth=BasicAuth(config.user, config.token)) as session:
            jql = "assignee = currentUser()"
            if open_sprint:
                jql += " AND sprint in (openSprints())"
            jql += " ORDER BY created"
            fields = "parent,priority,assignee,status,creator,subtasks,issuetype,project,created,updated,description,summary"
            data = await session.jql(jql, fields)
        for i in data["issues"]:
            print_formatted_text(FormattedText(summary_render(build_detailed_jira_issue(i))), style=style)

    loop = asyncio.new_event_loop()
    loop.run_until_complete(load_issue())


@pyjira.command(help="Show detailed information about a specific issue")
@click.argument('issue', nargs=1)
def show(issue: str):
    loop = asyncio.new_event_loop()

    async def load_issue():
        print("\n")
        config = _get_config()

        jira_issue: JiraIssue
        async with JiraClient(config, auth=BasicAuth(config.user, config.token)) as session:
            jira_issue = await session.issue(issue)

            await print_container(build_issue_container(jira_issue), style=style)

            if jira_issue.subtasks:
                await print_container(build_subtasks_container(jira_issue), style=style)

            comments = await session.comments(issue)
            if comments:
                await print_container(build_comments_container(comments), style=style)

            dev_status = await session.dev_status(jira_issue.internal_id)
            if dev_status.branches or dev_status.commits or dev_status.pull_requests:
                await print_container(build_dev_status_container(dev_status), style=style)

    loop.run_until_complete(load_issue())


@pyjira.command(help="Start an interactive dashboard")
def dashboard():
    config = _get_config()

    # Key bindings.
    bindings = KeyBindings()
    bindings.add("tab")(focus_next)
    bindings.add("s-tab")(focus_previous)

    def load_tree_elements(config: Config, tree: StyledTreeComponent, jql: str):
        @background_task
        async def load():
            data = await _load_data(config, jql)
            tree.set_values(data)
            get_app().invalidate()
            # TODO stop "thinking"
            # TODO disable "accept" from textArea

        # TODO show some sort of "thinking"
        # TODO disable "accept" from textArea
        load()

    @bindings.add("c-c")
    def shutdown(event: KeyPressEvent):
        " Pressing Ctrl-Q or Ctrl-C will exit the user interface. "
        event.app.exit()

    tree_key_bindings = KeyBindings()
    tree: StyledTreeComponent

    @tree_key_bindings.add("o")
    async def show_issue_details(event: KeyPressEvent):
        focus_window.body = await _load_issue_details(tree.get_selected_element().value.issue.id)
        get_app().invalidate()

    tree = StyledTreeComponent(values=[], external_key_bindings=tree_key_bindings)
    focus_window = Frame(title="Issue details", body=Label(""))

    def accept_text(buf: Buffer):
        load_tree_elements(config, tree, buf.text)
        return True

    dialog = HSplit([
        Frame(TextArea(config.board.filter.jql, accept_handler=accept_text, multiline=False), title="JQL",
              height=3),
        VSplit([Frame(tree, title="Board"), focus_window])
    ])

    application = Application(
        layout=Layout(dialog),
        key_bindings=merge_key_bindings([load_key_bindings(), bindings]),
        mouse_support=True,
        style=style,
        full_screen=True,
    )
    load_tree_elements(config, tree, config.board.filter.jql)
    application.run()


async def _load_data(config: Config, jql: str):
    async with JiraClient(config, auth=BasicAuth(config.user, config.token)) as session:
        data = await session.jql(jql,
                                 "parent,priority,assignee,status,creator,subtasks,issuetype,project,created,updated,description,summary")
        return _transform_to_view_data(data["issues"])


def _get_config_path() -> Path:
    if "PYJIRA_CONFIG" in os.environ:
        return Path(os.environ["PYJIRA_CONFIG"])
    return Path(os.path.join(os.path.expanduser("~"), ".pyjira.yaml"))


def _get_config() -> Config:
    config_path = _get_config_path()
    if not config_path.exists():
        quit(f"No configuration file found '{config_path.name}'. To configure, run the command 'configure'")
    return load_configuration(config_path)


async def _load_issue_details(id: str) -> Container:
    config = _get_config()

    issue: JiraIssue
    async with JiraClient(config, auth=BasicAuth(config.user, config.token)) as session:
        containers: List[AnyContainer] = []
        issue = await session.issue(id)
        containers.append(build_issue_container(issue))
        if issue.subtasks:
            containers.append(build_subtasks_container(issue))

        comments = await session.comments(id)
        if comments:
            containers.append(build_comments_container(comments))

        dev_status = await session.dev_status(issue.internal_id)
        if dev_status.branches or dev_status.commits or dev_status.pull_requests:
            containers.append(build_dev_status_container(dev_status)) # TODO this breaks sometimes

        return ScrollablePane(HSplit(containers))


@dataclass()
class JiraSummaryDrawable(Drawable):
    issue: JiraIssue

    def render(self) -> StyleAndTextTuples:
        return summary_render(self.issue)


class StyledTreeComponent(TreeComponent[JiraSummaryDrawable]):
    open_character = "["
    close_character = "]"
    container_style = "class:checkbox-list"
    default_style = "class:checkbox"
    selected_style = "class:checkbox-selected"
    checked_style = "class:checkbox-checked"


def _issue_to_view(issue) -> JiraSummaryDrawable:
    return JiraSummaryDrawable(build_summary_jira_issue(issue))


def _transform_to_view_data(raw_data) -> List[TreeElement[JiraSummaryDrawable]]:
    view_data: List[TreeElement[JiraSummaryDrawable]] = []
    for element in raw_data:
        view_data.append(TreeElement(
            value=_issue_to_view(element),
            children=_transform_to_view_data(element["fields"].get("subtasks", [])),
            expanded=False
        ))
    return view_data


if __name__ == "__main__":
    pyjira()
