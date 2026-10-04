"""Domain vocabulary shared by the scripted MockLLM policies and the verifier."""

SECTOR_KEYWORDS: dict[str, list[str]] = {
    "Information And Communications": ["tech", "technology", "ict", "infocomm", "information and communications",
                                       "digital", "software"],
    "Financial And Insurance Services": ["financ", "insurance", "banking"],
    "Manufacturing": ["manufactur"],
    "Construction": ["construction"],
    "Wholesale And Retail Trade": ["retail", "wholesale"],
    "Accommodation And Food Services": ["hospitality", "food services", "accommodation", "f&b"],
    "Transportation And Storage": ["transport", "logistics"],
    "Professional Services": ["professional services"],
}

# Order matters: "unemployment" must be tested before "employment".
METRIC_KEYWORDS: dict[str, list[str]] = {
    "unemployment": ["unemploy"],
    "retrenchment": ["retrench", "layoff", "lay-off", "laid off"],
    "vacancies": ["vacanc", "job openings"],
    "compensation": ["wage", "salary", "salaries", "compensation", "income"],
    "gdp": ["gdp", "value added", "economic output"],
    "programmes": ["programme", "program", "training", "enrol", "placement", "grant"],
    "employment": ["employ", "jobs", "workforce", "manpower", "headcount", "job market"],
}

# SingStat search text and the words the chosen table title must contain.
SINGSTAT_SEARCH: dict[str, tuple[str, list[str]]] = {
    "employment": ("employment by sector", ["employment", "sector"]),
    "retrenchment": ("retrenched employees by industry", ["retrenched", "industry"]),
    "vacancies": ("job vacancies by industry", ["vacancies", "industry"]),
    "compensation": ("compensation of employees by industry", ["compensation", "industry"]),
    "gdp": ("gross domestic product by industry", ["gross domestic product", "industry"]),
    "unemployment": ("unemployment rate", ["unemployment rate"]),
}

DATAGOV_SEARCH: dict[str, str] = {
    "retrenchment": "retrenched employees",
    "unemployment": "unemployment rate",
    "employment": "retrenched employees",  # labour-market cross-check alongside employment trends
}

ALL_SECTOR_NAMES = list(SECTOR_KEYWORDS)


def match_sectors(text: str) -> list[str]:
    low = text.lower()
    return [sector for sector, words in SECTOR_KEYWORDS.items() if any(w in low for w in words)]


def match_metrics(text: str) -> list[str]:
    low = text.lower()
    found = []
    for metric, words in METRIC_KEYWORDS.items():
        if any(w in low for w in words):
            if metric == "employment" and "unemploy" in low and not any(
                    w in low.replace("unemploy", "") for w in words):
                continue
            found.append(metric)
    return found
