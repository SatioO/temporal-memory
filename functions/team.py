from typing import Literal, TypedDict
from iii import IIIClient
from schema import TeamConfig
from state.kv import StateKV


class TeamSharePayload(TypedDict):
    item_id: str
    item_type: Literal["memory", "pattern", "observation"]
    session_id: str
    project: str


class TeamFeedPayload(TypedDict):
    limit: int


async def handle_team_share(data: TeamSharePayload):
    print(data)


async def handle_team_profile():
    print("team profile")


async def handle_team_feed(data: TeamFeedPayload):
    print(data)


def register_team_function(sdk: IIIClient, kv: StateKV, team_config: TeamConfig):
    sdk.register_function(
        {id: "[graphmind]::team-share"},
        handle_team_share
    )

    sdk.register_function(
        {id: "[graphmind]::team-feed"},
        handle_team_feed
    )

    sdk.register_function(
        {id: "[graphmind]::team-profile"},
        handle_team_profile
    )
