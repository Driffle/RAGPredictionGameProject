"""Recurring industry, sports, esports, and showcase windows for 2026–2030."""

from __future__ import annotations

from datetime import date, timedelta

from src.coverage import EXTRA_ANNUAL_EVENTS
from src.geo_placement import host_spec_for_event

# Typical annual merchandising windows. Live Wikipedia dates overwrite these
# when a year page confirms the edition.
ANNUAL_EVENTS = [
    {"name": "CES Gaming", "month": 1, "start_day": 7, "end_day": 11, "category": "PC / Hardware", "related_game": "NVIDIA, AMD, ASUS, Razer, Lenovo", "event_type": "Hardware Expo", "wikipedia": "Consumer_Electronics_Show"},
    {"name": "Nintendo Direct", "month": 2, "start_day": 18, "end_day": 18, "category": "Gaming", "related_game": "Nintendo franchises", "event_type": "Digital Showcase", "wikipedia": "Nintendo_Direct"},
    {"name": "Xbox Developer Direct", "month": 1, "start_day": 23, "end_day": 23, "category": "Gaming", "related_game": "Xbox / PC", "event_type": "Digital Showcase", "wikipedia": "Xbox_(brand)"},
    {"name": "PlayStation State of Play", "month": 1, "start_day": 30, "end_day": 30, "category": "Gaming", "related_game": "PlayStation", "event_type": "Digital Showcase", "wikipedia": "State_of_Play_(PlayStation)"},
    {"name": "IEM Katowice", "month": 1, "start_day": 20, "end_day": 15, "end_month": 2, "category": "Esports", "related_game": "Counter-Strike 2", "event_type": "Esports", "wikipedia": "Intel_Extreme_Masters"},
    {"name": "D.I.C.E. Awards", "month": 2, "start_day": 10, "end_day": 13, "category": "Gaming", "related_game": "Multi-platform", "event_type": "Awards", "wikipedia": "D.I.C.E._Awards"},
    {"name": "Taipei Game Show", "month": 2, "start_day": 5, "end_day": 9, "category": "Gaming / Anime", "related_game": "PC / Console / Mobile", "event_type": "Gaming Expo", "wikipedia": "Taipei_Game_Show"},
    {"name": "Six Invitational", "month": 2, "start_day": 8, "end_day": 16, "category": "Esports", "related_game": "Rainbow Six Siege", "event_type": "Esports", "wikipedia": "Six_Invitational"},
    {"name": "Steam Next Fest", "month": 2, "start_day": 24, "end_day": 3, "end_month": 3, "category": "Gaming", "related_game": "PC / Steam", "event_type": "Digital Festival", "wikipedia": "Steam_(service)"},
    {"name": "GDC", "month": 3, "start_day": 9, "end_day": 13, "category": "Gaming", "related_game": "PC / Console / Mobile", "event_type": "Developer Conference", "wikipedia": "Game_Developers_Conference"},
    {"name": "SXSW Gaming", "month": 3, "start_day": 13, "end_day": 21, "category": "Gaming / Entertainment", "related_game": "Multi-platform", "event_type": "Festival", "wikipedia": "South_by_Southwest"},
    {"name": "PAX East", "month": 3, "start_day": 26, "end_day": 29, "category": "Gaming", "related_game": "PC / Console", "event_type": "Gaming Expo", "wikipedia": "PAX_(event)"},
    {"name": "The Masters", "month": 4, "start_day": 6, "end_day": 12, "category": "Sports", "related_game": "PGA Tour 2K", "event_type": "Golf", "wikipedia": "Masters_Tournament"},
    {"name": "BAFTA Games Awards", "month": 4, "start_day": 8, "end_day": 8, "category": "Gaming", "related_game": "Multi-platform", "event_type": "Awards", "wikipedia": "British_Academy_Games_Awards"},
    {"name": "NBA Playoffs & Finals", "month": 4, "start_day": 15, "end_day": 20, "end_month": 6, "category": "Sports", "related_game": "NBA 2K", "event_type": "Basketball", "wikipedia": "NBA_playoffs"},
    {"name": "Stanley Cup Playoffs", "month": 4, "start_day": 15, "end_day": 20, "end_month": 6, "category": "Sports", "related_game": "NHL", "event_type": "Ice Hockey", "wikipedia": "Stanley_Cup_playoffs"},
    {"name": "IIHF World Championship", "month": 5, "start_day": 8, "end_day": 24, "category": "Sports", "related_game": "NHL", "event_type": "Ice Hockey", "wikipedia": "IIHF_World_Championship"},
    {"name": "League of Legends MSI", "month": 5, "start_day": 1, "end_day": 18, "category": "Esports", "related_game": "League of Legends", "event_type": "Esports", "wikipedia": "Mid-Season_Invitational"},
    {"name": "PGA Championship", "month": 5, "start_day": 14, "end_day": 17, "category": "Sports", "related_game": "PGA Tour 2K", "event_type": "Golf", "wikipedia": "PGA_Championship"},
    {"name": "Roland-Garros", "month": 5, "start_day": 24, "end_day": 7, "end_month": 6, "category": "Sports", "related_game": "Tennis games", "event_type": "Tennis", "wikipedia": "French_Open"},
    {"name": "Summer Game Fest", "month": 6, "start_day": 5, "end_day": 8, "category": "Gaming", "related_game": "Multi-platform", "event_type": "Showcase", "wikipedia": "Summer_Game_Fest", "status": "Confirmed"},
    {"name": "Xbox Games Showcase", "month": 6, "start_day": 8, "end_day": 8, "category": "Gaming", "related_game": "Xbox / PC", "event_type": "Platform Showcase", "wikipedia": "Xbox_Games_Showcase"},
    {"name": "PC Gaming Show", "month": 6, "start_day": 8, "end_day": 8, "category": "Gaming", "related_game": "PC", "event_type": "Showcase", "wikipedia": "PC_Gaming_Show"},
    {"name": "Capcom Showcase", "month": 6, "start_day": 9, "end_day": 9, "category": "Gaming", "related_game": "Resident Evil, Monster Hunter, Street Fighter", "event_type": "Publisher Showcase", "wikipedia": "Capcom"},
    {"name": "Ubisoft Forward", "month": 6, "start_day": 10, "end_day": 10, "category": "Gaming", "related_game": "Assassin's Creed, Far Cry, Rainbow Six", "event_type": "Publisher Showcase", "wikipedia": "Ubisoft_Forward"},
    {"name": "Nintendo Direct", "month": 6, "start_day": 18, "end_day": 18, "category": "Gaming", "related_game": "Mario, Zelda, Pokémon", "event_type": "Platform Showcase", "wikipedia": "Nintendo_Direct", "alias": "Nintendo Direct (June)"},
    {"name": "Steam Next Fest", "month": 6, "start_day": 9, "end_day": 16, "category": "Gaming", "related_game": "PC", "event_type": "Digital Festival", "wikipedia": "Steam_(service)", "alias": "Steam Next Fest (June)"},
    {"name": "WWDC", "month": 6, "start_day": 8, "end_day": 12, "category": "Technology / Gaming", "related_game": "Apple / Mac / iOS", "event_type": "Developer Conference", "wikipedia": "Worldwide_Developers_Conference"},
    {"name": "Tour de France", "month": 7, "start_day": 4, "end_day": 26, "category": "Sports", "related_game": "Cycling games", "event_type": "Cycling", "wikipedia": "Tour_de_France"},
    {"name": "EVO", "month": 7, "start_day": 31, "end_day": 3, "end_month": 8, "category": "Esports", "related_game": "Street Fighter, Tekken, Mortal Kombat", "event_type": "Fighting Games", "wikipedia": "Evolution_Championship_Series"},
    {"name": "Esports World Cup", "month": 7, "start_day": 7, "end_day": 24, "category": "Esports", "related_game": "Multi-game", "event_type": "Esports", "wikipedia": "Esports_World_Cup"},
    {"name": "ChinaJoy", "month": 7, "start_day": 31, "end_day": 3, "end_month": 8, "category": "Gaming / Anime", "related_game": "PC / Mobile / Console", "event_type": "Gaming Expo", "wikipedia": "ChinaJoy"},
    {"name": "Anime Expo", "month": 7, "start_day": 2, "end_day": 6, "category": "Anime / Gaming", "related_game": "Anime games / JRPG", "event_type": "Anime Convention", "wikipedia": "Anime_Expo"},
    {"name": "San Diego Comic-Con", "month": 7, "start_day": 23, "end_day": 26, "category": "Comics / TV / Movies / Gaming", "related_game": "Marvel, DC, Star Wars", "event_type": "Convention", "wikipedia": "San_Diego_Comic-Con"},
    {"name": "The Open Championship", "month": 7, "start_day": 16, "end_day": 19, "category": "Sports", "related_game": "PGA Tour 2K", "event_type": "Golf", "wikipedia": "The_Open_Championship"},
    {"name": "Gamescom", "month": 8, "start_day": 26, "end_day": 30, "category": "Gaming", "related_game": "Multi-platform", "event_type": "Gaming Expo", "wikipedia": "Gamescom", "status": "Confirmed"},
    {"name": "Gamescom Opening Night Live", "month": 8, "start_day": 25, "end_day": 25, "category": "Gaming", "related_game": "Multi-platform", "event_type": "Showcase", "wikipedia": "Gamescom", "status": "Confirmed"},
    {"name": "Future Games Show at Gamescom", "month": 8, "start_day": 26, "end_day": 30, "category": "Gaming", "related_game": "Multi-platform", "event_type": "Digital Showcase", "wikipedia": "Future_Games_Show"},
    {"name": "D23", "month": 8, "start_day": 14, "end_day": 16, "category": "Movies / TV / Comics / Gaming", "related_game": "Disney, Marvel, Star Wars", "event_type": "Fan Convention", "wikipedia": "D23_(Disney)"},
    {"name": "Pokémon World Championships", "month": 8, "start_day": 14, "end_day": 16, "category": "Gaming / Esports", "related_game": "Pokémon", "event_type": "Esports", "wikipedia": "Pokémon_World_Championships"},
    {"name": "Fortnite Global Championship", "month": 8, "start_day": 8, "end_day": 10, "category": "Esports", "related_game": "Fortnite", "event_type": "Esports", "wikipedia": "Fortnite_Championship_Series"},
    {"name": "VALORANT Champions", "month": 8, "start_day": 15, "end_day": 31, "category": "Esports", "related_game": "VALORANT", "event_type": "Esports", "wikipedia": "VALORANT_Champions"},
    {"name": "PAX West", "month": 8, "start_day": 28, "end_day": 31, "category": "Gaming", "related_game": "PC / PlayStation / Xbox / Nintendo", "event_type": "Gaming Expo", "wikipedia": "PAX_(event)"},
    {"name": "BlizzCon", "month": 9, "start_day": 12, "end_day": 13, "category": "Gaming / Esports", "related_game": "Warcraft, Diablo, Overwatch", "event_type": "Publisher Event", "wikipedia": "BlizzCon"},
    {"name": "Tokyo Game Show", "month": 9, "start_day": 17, "end_day": 21, "category": "Gaming / Anime", "related_game": "PC / PlayStation / Xbox / Nintendo / Anime", "event_type": "Gaming Expo", "wikipedia": "Tokyo_Game_Show", "status": "Confirmed"},
    {"name": "F1 World Championship", "month": 3, "start_day": 1, "end_day": 8, "end_month": 12, "category": "Sports", "related_game": "F1", "event_type": "Motorsport", "wikipedia": "Formula_One", "status": "Known cycle"},
    {"name": "NFL Season", "month": 9, "start_day": 4, "end_day": 8, "end_month": 2, "end_year_offset": 1, "category": "Sports", "related_game": "Madden NFL", "event_type": "American Football", "wikipedia": "National_Football_League", "status": "Known cycle"},
    {"name": "League of Legends Worlds", "month": 9, "start_day": 25, "end_day": 9, "end_month": 11, "category": "Esports", "related_game": "League of Legends", "event_type": "Esports", "wikipedia": "League_of_Legends_World_Championship"},
    {"name": "MLB Postseason", "month": 10, "start_day": 1, "end_day": 31, "category": "Sports", "related_game": "MLB The Show", "event_type": "Baseball", "wikipedia": "Major_League_Baseball_postseason"},
    {"name": "New York Comic Con", "month": 10, "start_day": 8, "end_day": 11, "category": "Comics / Movies / TV / Anime / Gaming", "related_game": "Marvel, DC, Star Wars, gaming adaptations", "event_type": "Convention", "wikipedia": "New_York_Comic_Con"},
    {"name": "MCM London Comic Con", "month": 10, "start_day": 23, "end_day": 25, "category": "Comics / Anime / TV / Movies / Gaming", "related_game": "Marvel, DC, Anime, Gaming", "event_type": "Convention", "wikipedia": "London_Comic_Con"},
    {"name": "Paris Games Week", "month": 10, "start_day": 28, "end_day": 1, "end_month": 11, "category": "Gaming", "related_game": "PlayStation / Xbox / Nintendo / PC", "event_type": "Gaming Expo", "wikipedia": "Paris_Games_Week"},
    {"name": "Steam Next Fest", "month": 10, "start_day": 13, "end_day": 20, "category": "Gaming", "related_game": "PC", "event_type": "Digital Festival", "wikipedia": "Steam_(service)", "alias": "Steam Next Fest (October)"},
    {"name": "Counter-Strike Major", "month": 11, "start_day": 5, "end_day": 16, "category": "Esports", "related_game": "Counter-Strike 2", "event_type": "Esports", "wikipedia": "Intel_Extreme_Masters"},
    {"name": "PUBG Global Championship", "month": 11, "start_day": 1, "end_day": 30, "category": "Esports", "related_game": "PUBG", "event_type": "Esports", "wikipedia": "PUBG_Global_Championship"},
    {"name": "Esports Awards", "month": 11, "start_day": 18, "end_day": 18, "category": "Esports", "related_game": "Multi-game", "event_type": "Awards", "wikipedia": "Esports_Awards"},
    {"name": "Golden Joystick Awards", "month": 11, "start_day": 20, "end_day": 20, "category": "Gaming", "related_game": "Multi-platform", "event_type": "Awards", "wikipedia": "Golden_Joystick_Awards"},
    {"name": "The Game Awards", "month": 12, "start_day": 10, "end_day": 10, "category": "Gaming / Awards", "related_game": "Multi-platform", "event_type": "Awards + Showcase", "wikipedia": "The_Game_Awards", "status": "Confirmed"},
    {"name": "Steam Winter Sale / Winter Events", "month": 12, "start_day": 18, "end_day": 5, "end_month": 1, "end_year_offset": 1, "category": "Gaming", "related_game": "PC / Steam", "event_type": "Digital Commerce", "wikipedia": "Steam_(service)"},
    {"name": "Steam Awards", "month": 12, "start_day": 18, "end_day": 31, "category": "Gaming", "related_game": "PC / Steam", "event_type": "Awards", "wikipedia": "Steam_Awards"},
    {"name": "Jump Festa", "month": 12, "start_day": 19, "end_day": 20, "category": "Anime / Manga / Gaming", "related_game": "Shonen Jump franchises", "event_type": "Anime Convention", "wikipedia": "Jump_Festa"},
]

ONE_OFF_EVENTS = [
    {
        "name": "2026 FIFA World Cup",
        "start": date(2026, 6, 11),
        "end": date(2026, 7, 19),
        "category": "Sports",
        "related_game": "EA Sports FC",
        "event_type": "Football",
        "status": "Confirmed",
        "wikipedia": "2026_FIFA_World_Cup",
    },
    {
        "name": "FIFA Women's World Cup",
        "start": date(2027, 6, 24),
        "end": date(2027, 7, 25),
        "category": "Sports",
        "related_game": "EA Sports FC",
        "event_type": "Football",
        "status": "Known cycle",
        "wikipedia": "2027_FIFA_Women%27s_World_Cup",
    },
    {
        "name": "2028 Summer Olympics",
        "start": date(2028, 7, 14),
        "end": date(2028, 7, 30),
        "category": "Sports",
        "related_game": "Olympic sports / multi-game",
        "event_type": "Multi-sport",
        "status": "Confirmed",
        "wikipedia": "2028_Summer_Olympics",
    },
    {
        "name": "UEFA Euro 2028",
        "start": date(2028, 6, 9),
        "end": date(2028, 7, 9),
        "category": "Sports",
        "related_game": "EA Sports FC",
        "event_type": "Football",
        "status": "Known cycle",
        "wikipedia": "UEFA_Euro_2028",
    },
    {
        "name": "FIFA World Cup 2030",
        "start": date(2030, 6, 8),
        "end": date(2030, 7, 21),
        "category": "Sports",
        "related_game": "EA Sports FC",
        "event_type": "Football",
        "status": "Known cycle",
        "wikipedia": "2030_FIFA_World_Cup",
    },
]


def _safe_date(year: int, month: int, day: int) -> date:
    for candidate in (day, 28, 1):
        try:
            return date(year, month, candidate)
        except ValueError:
            continue
    return date(year, month, 1)


def projected_events(years: range = range(2026, 2031)) -> list[dict]:
    rows: list[dict] = []
    for year in years:
        for spec in ANNUAL_EVENTS + EXTRA_ANNUAL_EVENTS:
            start = _safe_date(year, spec["month"], spec["start_day"])
            end_year = year + int(spec.get("end_year_offset") or 0)
            end_month = int(spec.get("end_month") or spec["month"])
            end = _safe_date(end_year, end_month, spec["end_day"])
            if end < start:
                end = start + timedelta(days=3)
            name = spec.get("alias") or spec["name"]
            host = host_spec_for_event(name) or host_spec_for_event(spec["name"])
            location = spec.get("location") or (host["location"] if host else "")
            mode = spec.get("mode") or (host["mode"] if host else "hybrid")
            scope = spec.get("scope") or (
                "global"
                if location.lower().split("·")[0].strip()
                in {"online", "worldwide", "global", "online / worldwide"}
                or (host and host["digital"])
                else "regional"
            )
            rows.append(
                {
                    "kind": "event",
                    "start_date": start.isoformat(),
                    "end_date": end.isoformat(),
                    "event": name,
                    "category": spec.get("category") or "Gaming",
                    "related_game": spec.get("related_game") or "Multi-platform",
                    "event_type": spec["event_type"],
                    "status": spec.get("status") or "Planning Window",
                    "wikipedia_url": (
                        f"https://en.wikipedia.org/wiki/{spec['wikipedia']}"
                        if spec.get("wikipedia")
                        else ""
                    ),
                    "source": "horizon_template",
                    "confirmation": spec.get("status") or "planning",
                    "attendance_mode": mode,
                    "scope": scope,
                    "location": location,
                    "organizer": spec.get("organizer") or "",
                    "cadence": "annual",
                }
            )
    for spec in ONE_OFF_EVENTS:
        host = host_spec_for_event(spec["name"])
        rows.append(
            {
                "kind": "event",
                "start_date": spec["start"].isoformat(),
                "end_date": spec["end"].isoformat(),
                "event": spec["name"],
                "category": spec["category"],
                "related_game": spec["related_game"],
                "event_type": spec["event_type"],
                "status": spec["status"],
                "wikipedia_url": f"https://en.wikipedia.org/wiki/{spec['wikipedia']}",
                "source": "horizon_template",
                "confirmation": spec["status"].lower(),
                "attendance_mode": spec.get("mode") or (host["mode"] if host else "physical"),
                "scope": spec.get("scope") or "global",
                "location": spec.get("location") or (host["location"] if host else ""),
                "organizer": spec.get("organizer") or "",
                "cadence": "one-off",
            }
        )
    return rows
