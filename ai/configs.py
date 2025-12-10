

prompt = """
You are an expert Site Reliability Engineer.

Classify the following error into one of: critical, high, medium, low.

Severity criteria:
- ~100% of users impacted → critical
- ~50% of users impacted → high
- Several users impacted → medium
- 1 user impacted → low

Examples of critical errors:
- Database connection failure
- Entire service unavailable

Examples of low-severity errors:
- Incorrect password
- Resource not found

Output format:
Return ONLY a JSON object:
{
  "severity": "<one_of_the_four>"
}

Log entry:
"""

candidate_labels = [ "medium", "low", "high", "critical", ]

hypothesis_template = "severity: {}"

system_prompt = """
You are an expert Site Reliability Engineer (SRE).
Your task is to analyze incoming Web-application log records and classify the incident severity.

Return your answer as a JSON object that follows exactly this schema:
{
  "severity": "<critical | high | medium | low>"
}

Rules:
- Severity is determined by user impact.
- You must return only valid severities.
- Do not include explanations or extra text.

"""