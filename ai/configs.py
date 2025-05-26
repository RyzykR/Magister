

prompt = (
    "You are an expert Site Reliability Engineer.\n"
    "Classify the following error into one of: critical, high, medium, low.\n\n"
    "Criteria:\n"
    "- 100% users impacted → critical\n"
    "- 1 user impacted → low\n\n"
    "Examples of critical errors:\n"
    "- Database connection failure\n"
    "- Service unavailable\n\n"
    "Examples of low-severity errors:\n"
    "- Incorrect password\n"
    "- Resource not found\n\n"
    "Return only the single word severity.\n"
    "Error:\n"
)

candidate_labels = [ "medium", "low", "high", "critical", ]

hypothesis_template = "severity: {}"
