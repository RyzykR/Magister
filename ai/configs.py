

prompt = (
    "You are an expert SRE. Evaluate the severity of the following error "
    "based on its potential impact on system availability, data integrity, "
    "and end user experience:\n\n"
)

candidate_labels = ["critical", "high", "medium", "low"]

hypothesis_template = "sverity: {}"
