"""Status check."""
import re
from typing import List

import requests
from bs4 import BeautifulSoup
from google_play_scraper import app as gplay_app
from google_play_scraper.exceptions import GooglePlayScraperException

from src.exceptions import APKMirrorScrapperFailure
from src.patches import Patches
from src.utils import (
    apk_mirror_base_url,
    apkmirror_status_check,
    bs4_parser,
    handle_github_response,
)

not_found_icon = "https://img.icons8.com/bubbles/500/android-os.png"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (HTML, like Gecko)"
    " Chrome/96.0.4664.93 Safari/537.36"
}


def apkcombo_scrapper(package_name: str) -> str:
    """Apkcombo scrapper."""
    try:
        apkcombo_url = f"https://apkcombo.com/genericApp/{package_name}"
        r = requests.get(apkcombo_url, headers=headers, allow_redirects=True)
        soup = BeautifulSoup(r.text, bs4_parser)
        url = soup.select_one("div.avatar > img")["data-src"]
        return re.sub(r"=.*$", "", url)
    except Exception:
        return not_found_icon


def apkmirror_scrapper(package_name: str) -> str:
    """Apkmirror URL."""
    response = apkmirror_status_check(package_name)
    if response["data"][0]["exists"]:
        search_url = f"{apk_mirror_base_url}/?s={package_name}"
        r = requests.get(search_url, headers=headers)
        soup = BeautifulSoup(r.text, bs4_parser)
        sub_url = soup.select_one("div.bubble-wrap > img")["src"]
        new_width = 500
        new_height = 500
        new_quality = 100

        # regular expression pattern to match w=xx&h=xx&q=xx
        pattern = r"(w=\d+&h=\d+&q=\d+)"

        return apk_mirror_base_url + re.sub(
            pattern, f"w={new_width}&h={new_height}&q={new_quality}", sub_url
        )
    raise APKMirrorScrapperFailure()


def gplay_icon_scrapper(package_name: str) -> str:
    """Scrap Icon from Gplay."""
    # noinspection PyBroadException
    try:
        result = gplay_app(
            package_name,
        )
        if result["icon"]:
            return str(result["icon"])
        raise GooglePlayScraperException()
    except GooglePlayScraperException:
        try:
            return apkmirror_scrapper(package_name)
        except APKMirrorScrapperFailure:
            return apkcombo_scrapper(package_name)
    except Exception:
        return not_found_icon


def generate_markdown_table(data: List[List[str]]) -> str:
    """Generate table."""
    if not data:
        return "No data to generate table."

    table = (
        "| Package Name | App Icon | PlayStore link | APKMirror link|APKCombo Link| Supported?|\n"
        + "|-------------|----------|----------------|---------------|------------------|----------|\n"
    )
    for row in data:
        if len(row) != 6:
            raise ValueError("Each row must contain 4 columns of data.")

        table += f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} |{row[4]} |{row[5]} |\n"

    return table


def main() -> None:
    repo_url = "https://api.revanced.app/v2/patches/latest"
    response = requests.get(repo_url)
    handle_github_response(response)

    parsed_data = response.json()
    compatible_packages = parsed_data["patches"]

    possible_apps = set()
    for package in compatible_packages:
        for compatible_package in package["compatiblePackages"]:
            possible_apps.add(compatible_package["name"])

    supported_app = set(Patches.support_app().keys())
    missing_support = sorted(possible_apps.difference(supported_app))
    output = "New app found which aren't supported or outdated.\n\n"
    data = [
        [
            app,
            f'<img src="{gplay_icon_scrapper(app)}" width=50 height=50>',
            f"[PlayStore Link](https://play.google.com/store/apps/details?id={app})",
            f"[APKMirror Link](https://www.apkmirror.com/?s={app})",
            f"[APKCombo Link](https://apkcombo.com/genericApp/{app})",
            "<li>- [ ] </li>",
        ]
        for app in missing_support
    ]
    table = generate_markdown_table(data)
    output += table
    with open("status.md", "w", encoding="utf_8") as status:
        status.write(output)
    print(output)


if __name__ == "__main__":
    main()
