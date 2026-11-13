"""Entry point for the five new Human-Agent workflow pilots."""
from . import human_agent_novel_case_runner as core

core.CASES.update({
    "edu-grade": "edu_grade",
    "media-library": "media_library",
    "facility-wo": "facility_wo",
    "volunteer-ops": "volunteer_ops",
    "garden-ops": "garden_ops",
})

if __name__ == "__main__":
    core.main()
