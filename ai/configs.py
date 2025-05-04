

prompt = (
    "You are an expert SRE. Evaluate the severity of the following error "
    "based on its potential impact on system availability, data integrity, "
    "and end users experience. Take into account number of users it could effect, errors affecting 100% users are critical, and for 1 it's low"
    "Error:\n\n"
)

candidate_labels = ["critical", "high", "medium", "low"]

hypothesis_template = "sverity: {}"
