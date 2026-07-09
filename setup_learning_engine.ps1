# Create engine folder
New-Item -ItemType Directory -Force "learning\engine" | Out-Null

# Create metadata.json
@'
{
    "id": "python_30_days",
    "title": "30 Days of Python",
    "provider": "Asabeneh Yetayeh",
    "category": "Python",
    "stat": "INT",
    "branch": "Software Engineering",
    "skill": "Python",
    "difficulty": "Beginner",
    "lessons": 30,
    "resource": "../../../resources/github/python/30-Days-Of-Python"
}
'@ | Set-Content "learning\tracks\software_engineering\python\30_days_of_python\metadata.json"

# Reset progress.json
@'
{
    "current_lesson": 2,
    "completed_lessons": [],
    "total_xp": 0,
    "status": "In Progress"
}
'@ | Set-Content "learning\tracks\software_engineering\python\30_days_of_python\progress.json"

# Create all 30 lesson folders
for ($i = 1; $i -le 30; $i++) {
    $day = "day_{0:D2}" -f $i
    $path = "learning\tracks\software_engineering\python\30_days_of_python\$day"

    New-Item -ItemType Directory -Force "$path\evidence" | Out-Null
    New-Item -ItemType File -Force "$path\notes.md" | Out-Null
    New-Item -ItemType File -Force "$path\solution.py" | Out-Null
    New-Item -ItemType File -Force "$path\reflection.md" | Out-Null
    New-Item -ItemType File -Force "$path\evidence\terminal_output.txt" | Out-Null
}

# Create starter engine files
New-Item -ItemType File -Force "learning\engine\tracker.py" | Out-Null
New-Item -ItemType File -Force "learning\engine\create_track.py" | Out-Null
New-Item -ItemType File -Force "learning\engine\xp.py" | Out-Null
New-Item -ItemType File -Force "learning\engine\metadata.py" | Out-Null
New-Item -ItemType File -Force "learning\engine\parser.py" | Out-Null