"""Github Downloader."""
import re
from typing import Dict, Tuple
from urllib.parse import urlparse

import requests
from loguru import logger

from src.config import RevancedConfig
from src.downloader.download import Downloader
from src.exceptions import PatchingFailed
from src.utils import handle_github_response, update_changelog


class Github(Downloader):
    """Files downloader."""

    def latest_version(self, app: str, **kwargs: Dict[str, str]) -> None:
        """Function to download files from GitHub repositories.

        :param app: App to download
        """
        logger.debug(f"Trying to download {app} from github")
        if self.config.dry_run or app == "microg":
            logger.debug(
                f"Skipping download of {app}. File already exists or dry running."
            )
            return
        owner = str(kwargs["owner"])
        repo_name = str(kwargs["name"])
        repo_url = f"https://api.github.com/repos/{owner}/{repo_name}/releases/latest"
        headers = {
            "Content-Type": "application/vnd.github.v3+json",
        }
        if self.config.personal_access_token:
            logger.debug("Using personal access token")
            headers["Authorization"] = f"token {self.config.personal_access_token}"
        response = requests.get(repo_url, headers=headers)
        handle_github_response(response)
        if repo_name == "revanced-patches":
            download_url = response.json()["assets"][1]["browser_download_url"]
        else:
            download_url = response.json()["assets"][0]["browser_download_url"]
        update_changelog(f"{owner}/{repo_name}", response.json())
        self._download(download_url, file_name=app)

    @staticmethod
    def _extract_repo_owner_and_tag(url: str) -> Tuple[str, str, str]:
        """Extract repo owner and url from github url."""
        parsed_url = urlparse(url)
        path_segments = parsed_url.path.strip("/").split("/")

        github_repo_owner = path_segments[0]
        github_repo_name = path_segments[1]

        release_tag = next(
            (
                f"tags/{path_segments[i + 1]}"
                for i, segment in enumerate(path_segments)
                if segment == "tag"
            ),
            "latest",
        )
        return github_repo_owner, github_repo_name, release_tag

    @staticmethod
    def _get_release_assets(
        github_repo_owner: str,
        github_repo_name: str,
        release_tag: str,
        asset_filter: str,
        config: RevancedConfig,
    ) -> str:
        """Get assets from given tag."""
        api_url = f"https://api.github.com/repos/{github_repo_owner}/{github_repo_name}/releases/{release_tag}"
        headers = {
            "Content-Type": "application/vnd.github.v3+json",
        }
        if config.personal_access_token:
            headers["Authorization"] = f"token {config.personal_access_token}"
        response = requests.get(api_url, headers=headers)
        handle_github_response(response)
        assets = response.json()["assets"]
        try:
            filter_pattern = re.compile(asset_filter)
        except re.error as e:
            raise PatchingFailed("Invalid regex pattern provided.") from e
        for asset in assets:
            assets_url = asset["browser_download_url"]
            assets_name = asset["name"]
            if match := filter_pattern.search(assets_url):
                logger.debug(f"Found {assets_name} to be downloaded from {assets_url}")
                return match.group()
        return ""

    @staticmethod
    def patch_resource(
        repo_url: str, assets_filter: str, config: RevancedConfig
    ) -> str:
        """Fetch patch resource from repo url."""
        repo_owner, repo_name, tag = Github._extract_repo_owner_and_tag(repo_url)
        return Github._get_release_assets(
            repo_owner, repo_name, tag, assets_filter, config
        )
