from __future__ import annotations

from typing import Optional, Dict, List, Union
import aiohttp
from pyjira.configuration import Config
import ssl
from dataclasses import dataclass


@dataclass()
class Branch:
    name: str
    url: str


@dataclass()
class Reviewer:
    name: str
    approved: bool


@dataclass()
class PullRequest:
    name: str
    url: str
    author_name: str
    comment_count: int
    destination: Branch
    reviewers: List[Reviewer]
    status: str


@dataclass()
class Commit:
    author_name: str
    url: str
    message: str
    id: str


@dataclass()
class DevStatus:
    branches: List[Branch]
    pull_requests: List[PullRequest]
    commits: List[Commit]


@dataclass()
class JiraIssue:
    id: str
    internal_id: str
    summary: str
    issue_type: str
    status: JiraStatus
    priority: str
    description: Optional[str] = None
    subtasks: Optional[List[JiraIssue]] = None
    parent: Optional[JiraIssue] = None
    assignee: Optional[JiraUser] = None
    creator: Optional[JiraUser] = None


@dataclass()
class JiraStatus:
    name: str
    state: str

@dataclass()
class JiraUser:
    id: str
    name: str


@dataclass()
class JiraComment:
    body: str
    author: JiraUser
    updated: str


class JiraClient(aiohttp.ClientSession):

    def __init__(self, config: Config, auth: Optional[aiohttp.BasicAuth] = None):
        self.config = config
        super().__init__(auth=auth)

    async def jql(self, jql: str, fields: str, expand: Optional[str] = "") -> Dict:#Coroutine[None, None, Dict[str, str]]:
        url = "/rest/api/latest/search"
        params = {
            "jql": jql,
            "fields": fields,
            "expand": expand,
        }
        return await self._ssl_request("GET", url, params)

    async def issue(self, id: str) -> JiraIssue:
        data = await self.jql(f"issue = {id}",
                       "parent,priority,assignee,status,creator,subtasks,issuetype,project,created,updated,description,summary",
                              expand="renderedFields")
        with open("issue.json", "w") as file:
            import json
            file.write(json.dumps(data))
        return build_detailed_jira_issue(data["issues"][0])

    async def comments(self, id: str) -> List[JiraComment]:
        url = f"/rest/api/latest/issue/{id}/comment"
        params = {
            "orderBy": "created"
        }
        data = await self._ssl_request("GET", url, params)
        return [_build_jira_comment(c) for c in data["comments"]]

    async def dev_status(self, internalId: str) -> DevStatus:
        url = "/rest/dev-status/1.0/issue/detail"
        params = {
            "issueId": internalId,
            "applicationType": "stash",
            "dataType": "pullrequest"
        }
        data = await self._ssl_request("GET", url, params)

        branches: List[Branch] = []
        for branch in data["detail"][0]["branches"]:
            branches.append(_build_branch(branch))

        pull_requests: List[PullRequest] = []
        for pull_request in data["detail"][0]["pullRequests"]:
            reviewers: List[Reviewer] = []
            for reviewer in pull_request["reviewers"]:
                reviewers.append(Reviewer(name=reviewer["name"], approved=reviewer["approved"]))
            pull_requests.append(PullRequest(
                name=pull_request["name"],
                url=pull_request["url"],
                reviewers=reviewers,
                author_name=pull_request["author"]["name"],
                comment_count=pull_request["commentCount"],
                destination=Branch(name=pull_request["source"]["branch"], url=pull_request["source"]["url"]),
                status=pull_request["status"]))

        commits: List[Commit] = []
        params["dataType"] = "repository"
        data = await self._ssl_request("GET", url, params)
        for repo in data["detail"][0]["repositories"]:
            for commit in repo["commits"]:
                commits.append(Commit(
                    author_name=commit["author"]["name"],
                    message=commit["message"],
                    url=commit["url"],
                    id=commit["displayId"],
                ))

        return DevStatus(pull_requests=pull_requests, branches=branches, commits=commits)

    async def _ssl_request(self, method: str, url: str, params: Dict) -> Dict:
        url = self.config.jira_base_url + url
        ssl_context = ssl.create_default_context(
            cafile=self.config.cert_path)
        async with self.request(method, url, params=params, ssl=ssl_context) as response:
            return await response.json()


def _build_jira_comment(comment: Dict) -> JiraComment:
    return JiraComment(body=comment["body"],
                       author=_build_jira_user(comment["author"]),
                       updated=comment["updated"])


def _build_summary_jira_issue_arguments(issue: Dict) -> Dict:
    fields = issue["fields"]
    return {
        "id": issue["key"],
        "internal_id": issue["id"],
        "summary": fields["summary"],
        "issue_type": fields["issuetype"]["name"],
        "priority": fields["priority"]["name"],
        "status": JiraStatus(name=fields["status"]["name"], state=fields["status"]["statusCategory"]["key"])
    }


def _build_detailed_jira_issue_arguments(issue: Dict) -> Dict:
    summary_arguments = _build_summary_jira_issue_arguments(issue)
    fields = issue["fields"]
    detailed_arguments = {
        "description": issue["renderedFields"]["description"] if "renderedFields" in issue else fields["description"]
    }
    if "parent" in fields:
        detailed_arguments["parent"] = build_summary_jira_issue(fields["parent"])
    if "subtasks" in fields:
        detailed_arguments["subtasks"] = [build_summary_jira_issue(i) for i in fields["subtasks"]]
    if "assignee" in fields:
        detailed_arguments["assignee"] = _build_jira_user(fields["assignee"])
    if "creator" in fields:
        detailed_arguments["creator"] = _build_jira_user(fields["creator"])
    return summary_arguments | detailed_arguments


def _build_jira_user(user: Dict) -> Union[JiraUser, None]:
    if not user:
        return None
    return JiraUser(id=user["name"], name=user["displayName"])


def build_detailed_jira_issue(issue: Dict) -> JiraIssue:
    return JiraIssue(**_build_detailed_jira_issue_arguments(issue))


def build_summary_jira_issue(issue: Dict) -> JiraIssue:
    return JiraIssue(**_build_summary_jira_issue_arguments(issue))


def _build_branch(branch: Dict) -> Branch:
    return Branch(name=branch["name"], url=branch["url"])

