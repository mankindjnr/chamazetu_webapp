contributions = {
    "23-05-2024": {
        "kispo zimlu": {"24-04-2024": 15670},
        "vukko zopsi": {"23-05-2024": 0},
    },
    "23-04-2024": {
        "vukko zopsi": {"22-04-2024": 1357756},
        "kispo zimlu": {"23-04-2024": 520070},
    },
}

for key, value in contributions.items():
    print("===", key)
    for name, contribution in value.items():
        print(name)
        for date, amount in contribution.items():
            print(date, amount)
